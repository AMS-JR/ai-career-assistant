# =============================================
# agent_tools.arbeitnow
# =============================================

import json
import logging
from typing import Any

from agents import function_tool

from agent_tools.http_client import get_job_http_client
from utils.job_api_cache import get_cached_job_list
from utils.llm_payload import trim_api_jobs_for_llm
from utils.job_recency import filter_raw_jobs_by_recency
from utils.settings import (
    get_job_api_cache_ttl_seconds,
    get_job_listing_max_age_days,
    get_job_tool_description_max_chars,
    get_job_tool_max_results,
)

logger = logging.getLogger(__name__)

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


def _arbeitnow_params(
    *,
    page: int,
    remote_only: bool,
    visa_sponsorship: bool | None,
) -> dict[str, Any]:
    p = max(1, int(page))
    params: dict[str, Any] = {"page": p}
    if remote_only:
        params["remote"] = "true"
    if visa_sponsorship is True:
        params["visa_sponsorship"] = "true"
    elif visa_sponsorship is False:
        params["visa_sponsorship"] = "false"
    return params


def _fetch_arbeitnow_raw(params: dict[str, Any]) -> list:
    cache_key = f"arbeitnow:{json.dumps(params, sort_keys=True, default=str)}"
    ttl = get_job_api_cache_ttl_seconds()

    def fetch() -> list:
        try:
            client = get_job_http_client()
            response = client.get(ARBEITNOW_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.warning("Arbeitnow fetch failed (params=%s): %s", params, e)
            return []

    return get_cached_job_list(cache_key, ttl, fetch)


def fetch_arbeitnow_jobs_sync(
    page: int = 1,
    *,
    remote_only: bool = False,
    visa_sponsorship: bool | None = None,
) -> list[dict]:
    """
    Fetch trimmed Arbeitnow listings (same query params as the agent tool).
    """
    params = _arbeitnow_params(
        page=page, remote_only=remote_only, visa_sponsorship=visa_sponsorship
    )
    raw = _fetch_arbeitnow_raw(params)
    raw = filter_raw_jobs_by_recency(
        raw,
        arbeitnow=True,
        max_age_days=get_job_listing_max_age_days(),
    )
    return trim_api_jobs_for_llm(
        raw,
        max_items=get_job_tool_max_results(),
        description_max_chars=get_job_tool_description_max_chars(),
        arbeitnow=True,
    )


def fetch_arbeitnow_feed_page_sync(page: int) -> list[dict]:
    """One page of the raw feed (~100 jobs) for ranking / fallback (untrimmed)."""
    params = _arbeitnow_params(page=page, remote_only=False, visa_sponsorship=None)
    return _fetch_arbeitnow_raw(params)


@function_tool
def fetch_arbeitnow_jobs(
    page: int = 1,
    remote_only: bool = False,
    require_visa_sponsorship: bool = False,
) -> list:
    """
    Fetch job listings from Arbeitnow's public Job Board API (no API key).

    The API returns a **paged feed**. It does **not** reliably filter by arbitrary
    keyword search—use **page** (and optional filters) instead.

    Args:
        page: Page number (1-based). Call with page=1, then 2, then 3, etc. to scan more listings.
        remote_only: If true, pass ``remote=true`` to the API (remote-focused postings).
        require_visa_sponsorship: If true, pass ``visa_sponsorship=true`` to the API.

    Returns:
        Trimmed job dicts with: slug, title, company_name, location, remote, tags, job_types,
        description (plain text, truncated), url, created_at (unix seconds).
        Rows older than ``JOB_LISTING_MAX_AGE_DAYS`` (default 90) are dropped when ``created_at`` is present.
    """
    visa: bool | None = True if require_visa_sponsorship else None
    return fetch_arbeitnow_jobs_sync(
        page, remote_only=remote_only, visa_sponsorship=visa
    )
