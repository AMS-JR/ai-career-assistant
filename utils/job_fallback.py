# =============================================
# career_agents.job_fallback - direct API listings when LLM matchers return nothing
# =============================================

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from agent_tools.arbeitnow import fetch_arbeitnow_feed_page_sync
from agent_tools.remotive import fetch_remotive_jobs_sync
from utils.job_recency import filter_raw_jobs_by_recency
from utils.llm_payload import strip_html_to_text
from utils.settings import (
    get_arbeitnow_fallback_max_pages,
    get_job_listing_max_age_days,
)

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset(
    "the and for with from this that have has been were will your our are was "
    "but not you all can her one may out day get use man new now way may any "
    "who its say per via cum bei und der die das von mit eine einem einen auch "
    "sind sich nicht als des zur zum".split()
)

_TECH_TITLE = re.compile(
    r"\b(engineer|developer|entwickler|software|backend|frontend|full[\s-]?stack|devops|"
    r"sre|programmer|programmierer|data\s+scien|machine\s+learning|mlops|cloud|sysadmin|"
    r"informatik|it[-\s]?consult|kubernetes|python|java|typescript|javascript)\b",
    re.I,
)


def profile_search_queries(profile: dict[str, Any]) -> list[str]:
    """Build short search strings from parsed profile (used as API `search` params)."""
    candidates: list[str] = []
    skills = profile.get("skills")
    if isinstance(skills, list) and skills:
        chunk = " ".join(str(s).strip() for s in skills[:8] if s)
        if len(chunk) > 2:
            candidates.append(chunk[:100])
    title = profile.get("title")
    if isinstance(title, str) and title.strip():
        candidates.append(title.strip()[:100])
    summary = profile.get("summary")
    if isinstance(summary, str) and summary.strip():
        words = [w for w in summary.replace("/", " ").split() if len(w) > 2][:10]
        if words:
            candidates.append(" ".join(words)[:100])
    if not candidates:
        candidates.append("software engineer")
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out[:4]


def _profile_tokens(profile: dict[str, Any]) -> set[str]:
    parts: list[str] = []
    for k in ("title", "summary", "headline", "current_role"):
        v = profile.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)
    sk = profile.get("skills")
    if isinstance(sk, list):
        parts.extend(str(s) for s in sk if s)
    blob = " ".join(parts).lower()
    tokens: set[str] = set()
    for m in re.finditer(r"[a-z0-9][a-z0-9+#.\-]{1,}", blob):
        w = m.group(0).strip(".-")
        if len(w) > 2 and w not in _STOP_WORDS:
            tokens.add(w)
    return tokens


def _arbeitnow_relevance_score(raw: dict[str, Any], tokens: set[str]) -> float:
    title = (raw.get("title") or "").lower()
    if not tokens:
        return 1.0 if _TECH_TITLE.search(raw.get("title") or "") else 0.0
    desc = strip_html_to_text(raw.get("description"), 2800).lower()
    tag_blob = " ".join(str(t).lower() for t in (raw.get("tags") or []) if t)
    hay = f"{desc} {tag_blob}"
    score = 0.0
    for t in tokens:
        if t in title:
            score += 4.0
        elif t in hay:
            score += 1.0
    if score == 0.0 and _TECH_TITLE.search(raw.get("title") or ""):
        score = 0.5
    return score


def ranked_arbeitnow_raw_jobs(
    profile: dict[str, Any], *, max_pages: int | None = None, cap: int = 22
) -> list[dict[str, Any]]:
    """
    Arbeitnow's HTTP API returns a general feed; query-string ``search`` does not filter.
    Pull several pages and rank rows against profile tokens.
    """
    pages = max_pages if max_pages is not None else get_arbeitnow_fallback_max_pages()
    tokens = _profile_tokens(profile)
    scored: list[tuple[float, dict[str, Any]]] = []
    max_age = get_job_listing_max_age_days()
    for page in range(1, pages + 1):
        chunk = fetch_arbeitnow_feed_page_sync(page)
        for raw in filter_raw_jobs_by_recency(chunk, arbeitnow=True, max_age_days=max_age):
            if isinstance(raw, dict):
                scored.append((_arbeitnow_relevance_score(raw, tokens), raw))
    scored.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s, raw in scored:
        if s < 0.5:
            continue
        u = str(raw.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(raw)
        if len(out) >= cap:
            break
    return out


# Backwards-compatible name for internal use
_arbeitnow_ranked_jobs = ranked_arbeitnow_raw_jobs


def _normalized_job(raw: dict[str, Any], source: str) -> dict[str, Any]:
    company = raw.get("company") or raw.get("company_name") or "-"
    loc = raw.get("location") or raw.get("candidate_required_location") or ""
    if not isinstance(loc, str):
        loc = str(loc)
    if not loc.strip():
        loc = "See listing"
    url = str(raw.get("url") or "").strip() or "#"
    desc = strip_html_to_text(raw.get("description"), 400)
    return {
        "title": raw.get("title") or "Job",
        "company": company,
        "location": loc,
        "description": desc,
        "url": url,
        "source": source,
        "overall_match_score": 72,
        "skill_match_percentage": 72,
        "matching_skills": [],
        "missing_critical_skills": [],
        "why_this_match": "Live listing from the job board (keyword search from your profile).",
    }


def _remotive_rows_fallback(profile: dict[str, Any]) -> list[dict[str, Any]]:
    queries = profile_search_queries(profile)
    primary = queries[0]

    remotive_rows = fetch_remotive_jobs_sync(primary, "software-dev", 25)
    if len(remotive_rows) < 8:
        remotive_rows = list(remotive_rows) + fetch_remotive_jobs_sync(primary, "", 25)
    for q in queries[1:3]:
        if len(remotive_rows) >= 20:
            break
        remotive_rows = list(remotive_rows) + fetch_remotive_jobs_sync(q, "software-dev", 15)
        remotive_rows = list(remotive_rows) + fetch_remotive_jobs_sync(q, "", 15)

    remotive_seen: set[str] = set()
    remotive_unique: list[dict[str, Any]] = []
    for row in remotive_rows:
        u = str(row.get("url") or "").strip()
        if u and u not in remotive_seen:
            remotive_seen.add(u)
            remotive_unique.append(row)
    return remotive_unique


def _merge_fallback_normalized(
    remotive_rows: list[dict[str, Any]],
    arbeitnow_raw: list[dict[str, Any]],
    *,
    primary_query: str,
    extra_queries: list[str],
) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    out: list[dict[str, Any]] = []

    for row in remotive_rows:
        u = str(row.get("url") or "").strip()
        if u and u not in seen_urls and u != "#":
            seen_urls.add(u)
            out.append(_normalized_job(row, "Remotive"))

    for raw in arbeitnow_raw:
        u = str(raw.get("url") or "").strip()
        if u and u not in seen_urls and u != "#":
            seen_urls.add(u)
            out.append(_normalized_job(raw, "Arbeitnow"))

    logger.info(
        "Direct job board fetch: %d listings (primary_query=%r, extra_queries=%s)",
        len(out),
        primary_query,
        extra_queries,
    )
    return out[:40]


def fetch_fallback_jobs_sync(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Call Remotive (search works) and Arbeitnow (paged feed + client-side rank) without an LLM.
    Used when matcher agents return an empty list so the UI still shows real openings.
    """
    queries = profile_search_queries(profile)
    rem = _remotive_rows_fallback(profile)
    arb = ranked_arbeitnow_raw_jobs(profile)
    return _merge_fallback_normalized(rem, arb, primary_query=queries[0], extra_queries=queries[1:3])


async def fetch_fallback_jobs_async(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Same as ``fetch_fallback_jobs_sync`` but Remotive and Arbeitnow work run in parallel."""
    queries = profile_search_queries(profile)
    rem, arb = await asyncio.gather(
        asyncio.to_thread(_remotive_rows_fallback, profile),
        asyncio.to_thread(ranked_arbeitnow_raw_jobs, profile),
    )
    return _merge_fallback_normalized(rem, arb, primary_query=queries[0], extra_queries=queries[1:3])
