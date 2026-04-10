# =============================================
# career_agents.remotive_matcher
# =============================================

import logging
import re

from agents import Agent, Runner

from agent_tools.remotive import fetch_remotive_jobs, fetch_remotive_jobs_sync
from utils.job_fallback import profile_search_queries
from utils.matcher_shared import parse_llm_job_array
from utils.agent_llm_kw import agent_kwargs_basic
from utils.llm_payload import profile_json_for_llm
from utils.settings import (
    get_job_tool_max_results,
    get_matcher_max_turns,
    get_matcher_min_overall_score,
    get_matcher_min_skill_percent,
    get_matcher_profile_json_max_chars,
    get_remotive_reconcile_query_cap,
)

logger = logging.getLogger(__name__)

_REMOTIVE_HOST = re.compile(r"remotive\.(com|io)", re.I)
_REMOTIVE_ID_TAIL = re.compile(r"-(\d+)$")
_REMOTIVE_ID_ONLY = re.compile(r"/(\d+)$")


def _norm_title_company(title: str, company: str) -> tuple[str, str]:
    def n(s: str) -> str:
        s = (s or "").lower().strip()
        return re.sub(r"\s+", " ", s)

    return (n(title), n(company))


def _remotive_numeric_id_from_url(url: str) -> int | None:
    """Remotive listing URLs end with ``...-jobid`` or rarely ``/jobid``; id-only paths 404 on the site."""
    if not url or not _REMOTIVE_HOST.search(url):
        return None
    base = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    m = _REMOTIVE_ID_TAIL.search(base) or _REMOTIVE_ID_ONLY.search(base)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _build_remotive_canonical_maps(profile: dict) -> tuple[dict[int, str], dict[tuple[str, str], str]]:
    """Map Remotive API ``id`` and (title, company) to the canonical ``url`` (same queries as fallback; HTTP cache applies)."""
    cap_tool = get_job_tool_max_results()
    by_id: dict[int, str] = {}
    by_key: dict[tuple[str, str], str] = {}
    for q in profile_search_queries(profile)[: get_remotive_reconcile_query_cap()]:
        for cat in ("software-dev", None):
            batch = fetch_remotive_jobs_sync(q, cat, cap_tool)
            for row in batch:
                if not isinstance(row, dict):
                    continue
                u = str(row.get("url") or "").strip()
                if not u:
                    continue
                raw_id = row.get("id")
                try:
                    if raw_id is not None:
                        by_id[int(raw_id)] = u
                except (TypeError, ValueError):
                    pass
                t = str(row.get("title") or "")
                c = str(row.get("company") or row.get("company_name") or "")
                k = _norm_title_company(t, c)
                if k[0] and k not in by_key:
                    by_key[k] = u
    return by_id, by_key


def _reconcile_remotive_job_urls(
    jobs: list,
    by_id: dict[int, str],
    by_key: dict[tuple[str, str], str],
) -> list:
    """Replace hallucinated or truncated Remotive links with URLs from the live API index."""
    out: list = []
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        job = dict(raw)
        url = str(job.get("url") or "").strip()
        src = str(job.get("source") or "")
        is_remotive = src.strip().lower() == "remotive" or (
            url and _REMOTIVE_HOST.search(url) is not None
        )
        if not is_remotive:
            out.append(job)
            continue
        canonical: str | None = None
        raw_job_id = job.get("id")
        try:
            if raw_job_id is not None:
                canonical = by_id.get(int(raw_job_id))
        except (TypeError, ValueError):
            pass
        if not canonical:
            rid = _remotive_numeric_id_from_url(url)
            if rid is not None and rid in by_id:
                canonical = by_id[rid]
        if not canonical:
            k = _norm_title_company(str(job.get("title") or ""), str(job.get("company") or ""))
            if k[0]:
                canonical = by_key.get(k)
        if canonical:
            job["url"] = canonical
        out.append(job)
    return out


def _instructions(profile_json: str) -> str:
    ms = get_matcher_min_skill_percent()
    mo = get_matcher_min_overall_score()
    return f"""You are an expert job-matching assistant. You **must** use the **fetch_remotive_jobs** tool to load listings; do not invent jobs.

    **Candidate profile (JSON):**
    {profile_json}

    **Step 1 — Call the Remotive tool (one or more times)**
    - **Pagination:** Remotive's public API has **no page/offset**—only ``search``, ``category``, ``limit``.
      To see more distinct listings, use **multiple tool calls** with different **search** strings (and optionally ``category=""`` for all categories). The API returns jobs sorted by **publication_date**; very old rows are already filtered server-side in the tool when dates exist.
    - Build **search** from the profile: job title, headline, top skills, and summary keywords (e.g. "senior python backend", "kubernetes aws").
    - **Speed:** Prefer **1–3** focused tool calls total; add another only if the first call returned clearly too few rows.
    - Set **category** to **exactly one** slug from this list (invalid slugs are coerced to **software-dev**):
      software-dev, data, devops, design, marketing, product, sales, customer-support,
      finance-legal, hr, copywriting, business, teaching, medical-healthcare, legal, other.
      Most software engineers → **software-dev**. Data/ML → **data**. Platform/SRE → **devops**.
    - Use **limit** up to the tool maximum. If results are thin, call again with a **broader search** or **category=""** (empty string) for a wider net, or a different slug if the profile clearly fits another category.

    **Step 2 — Score each returned job**
    **a) skill_match_percentage (0–100)** — overlap of candidate skills vs job description/tags (technical skills weighted).
    **b) overall_match_score (0–100)** — ~60% skills, ~20% seniority/title fit, ~15% role alignment, ~5% education; small bonuses/penalties.

    **Step 3 — Filtering**
    Prefer skill_match_percentage ≥ {ms} and overall_match_score ≥ {mo}.
    If that removes almost everything, still return the **best matches you have** (do not return an empty array unless the tool truly returned no rows).

    **Step 4 — Final answer (no more tool calls)**
    Return **only** a JSON array, sorted by overall_match_score descending. Each object:
    - title, company, location (from candidate_required_location or "Remote"),
    - description (plain text, max 250 chars), **url** (copy **exactly** from tool output—full ``https://remotive.com/remote-jobs/...`` path; do not shorten or rewrite),
    - **id** (integer from tool output, when present),
    - source = "Remotive",
    - skill_match_percentage, overall_match_score,
    - matching_skills (array), missing_critical_skills (array), why_this_match (1–2 sentences).

    Optional ```json code fence is allowed; no other prose in the final message.
    """


def _direct_remotive_fallback(profile: dict) -> list:
    """Same HTTP as the tool, without an LLM—used when the agent returns no usable JSON or empty matches."""
    cap_tool = get_job_tool_max_results()
    seen: set[str] = set()
    out: list = []
    for q in profile_search_queries(profile)[:4]:
        for cat in ("software-dev", None):
            batch = fetch_remotive_jobs_sync(q, cat, cap_tool)
            for row in batch:
                if not isinstance(row, dict):
                    continue
                u = str(row.get("url") or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                loc = row.get("candidate_required_location") or "Remote"
                out.append(
                    {
                        "title": row.get("title") or "Job",
                        "company": row.get("company") or row.get("company_name") or "-",
                        "location": str(loc),
                        "description": str(row.get("description") or "")[:400],
                        "url": u,
                        "source": "Remotive",
                        "overall_match_score": 70,
                        "skill_match_percentage": 70,
                        "matching_skills": [],
                        "missing_critical_skills": [],
                        "why_this_match": "Live Remotive listing (direct fetch; agent returned no scored rows).",
                    }
                )
                if len(out) >= 18:
                    return out
    return out


async def match_remotive_jobs(profile: dict) -> list:
    """Agent uses ``fetch_remotive_jobs`` as a tool, then returns scored JSON matches."""
    profile_json = profile_json_for_llm(profile, get_matcher_profile_json_max_chars())
    agent = Agent(
        name="RemotiveMatcher",
        instructions=_instructions(profile_json),
        tools=[fetch_remotive_jobs],
        **agent_kwargs_basic(),
    )

    result = await Runner.run(
        agent,
        "Use fetch_remotive_jobs with search and category derived from the profile, then return the final JSON array of scored matches.",
        max_turns=get_matcher_max_turns(),
    )

    parsed = parse_llm_job_array(result.final_output or "")
    if parsed:
        by_id, by_key = _build_remotive_canonical_maps(profile)
        return _reconcile_remotive_job_urls(parsed, by_id, by_key)

    logger.info("Remotive matcher: no scored JSON from agent; running direct Remotive HTTP fallback.")
    return _direct_remotive_fallback(profile)
