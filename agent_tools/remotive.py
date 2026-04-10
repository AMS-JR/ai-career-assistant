# =============================================
# agent_tools.remotive
# =============================================

import json
import logging
import time

import httpx

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

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"

REMOTIVE_CATEGORY_SLUGS = (
    "software-dev",
    "data",
    "devops",
    "design",
    "marketing",
    "product",
    "sales",
    "customer-support",
    "finance-legal",
    "hr",
    "copywriting",
    "business",
    "teaching",
    "medical-healthcare",
    "legal",
    "other",
)


def coerce_remotive_category_slug(category: str | None) -> str | None:
    """Remotive accepts slugs from their categories list; unknown values fall back to ``software-dev``."""
    c = (category or "").strip().lower()
    if not c:
        return None
    if c in REMOTIVE_CATEGORY_SLUGS:
        return c
    logger.warning("Unknown Remotive category %r; using software-dev", category)
    return "software-dev"


def fetch_remotive_jobs_sync(
    search: str,
    category: str | None = "software-dev",
    limit: int = 25,
) -> list[dict]:
    """
    Fetch and trim Remotive listings. Category may be omitted (empty string or None) to search all remote jobs.
    """
    cap = get_job_tool_max_results()
    limit_clamped = min(max(1, int(limit)), cap)
    params: dict[str, str | int] = {
        "search": (search or "").strip() or "developer",
        "limit": limit_clamped,
    }
    cat = coerce_remotive_category_slug(category)
    if cat:
        params["category"] = cat

    cache_key = f"remotive:{json.dumps(params, sort_keys=True)}"
    ttl = get_job_api_cache_ttl_seconds()

    def fetch() -> list:
        client = get_job_http_client()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = client.get(REMOTIVE_URL, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("jobs", [])
            except httpx.HTTPStatusError as e:
                last_err = e
                code = e.response.status_code if e.response is not None else 0
                if code >= 500 and attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                logger.warning("Remotive HTTP error: %s", e)
                return []
            except Exception as e:
                last_err = e
                logger.warning("Remotive fetch failed: %s", e)
                return []
        if last_err:
            logger.warning("Remotive fetch gave up: %s", last_err)
        return []

    # Do not cache empty responses — avoids pinning 502/empty results for the TTL.
    raw = get_cached_job_list(cache_key, ttl, fetch, cache_empty=False)
    raw = filter_raw_jobs_by_recency(
        raw,
        arbeitnow=False,
        max_age_days=get_job_listing_max_age_days(),
    )
    return trim_api_jobs_for_llm(
        raw,
        max_items=cap,
        description_max_chars=get_job_tool_description_max_chars(),
        arbeitnow=False,
    )


@function_tool
def fetch_remotive_jobs(search: str, category: str = "software-dev", limit: int = 25) -> list:
    """
    Fetch remote job listings from Remotive's public API (GET /api/remote-jobs).

    Args:
        search: Free-text search string—use keywords from the candidate's target role and skills
            (e.g. "python backend engineer", "react typescript", "data pipeline").
        category: Exactly one Remotive category slug (required for focused results). Valid slugs:
            software-dev, data, devops, design, marketing, product, sales, customer-support,
            finance-legal, hr, copywriting, business, teaching, medical-healthcare, legal, other.
            Pick the slug that best matches the candidate's profession. Use an empty string "" to
            omit category and search across all remote jobs (broader, noisier).
        limit: Max jobs to return (capped for context size; default 25). The public API has **no
            page/offset**—wider coverage = multiple tool calls with different ``search`` (and/or ``category``).
            Results are sorted by **publication_date** on Remotive's side.

    Returns:
        Trimmed job dicts: id, title, company, candidate_required_location, job_type, tags,
        description (plain text, truncated), url, posted_at / publication_date, created_at.
        Rows older than ``JOB_LISTING_MAX_AGE_DAYS`` (default 90) are dropped when dates are present.
    """
    return fetch_remotive_jobs_sync(search, category or None, limit)
