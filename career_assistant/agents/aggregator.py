# =============================================
# career_assistant.agents.aggregator
# =============================================

import asyncio
import json
import logging
import re

from agents import Agent, Runner

from career_assistant.agents.arbeitnow_matcher import match_arbeitnow_jobs
from career_assistant.agents.job_fallback import fetch_fallback_jobs_sync
from career_assistant.agents.remotive_matcher import match_remotive_jobs
from career_assistant.utils.settings import (
    get_agent_max_turns,
    get_aggregator_description_max_chars,
    get_aggregator_max_jobs,
)

logger = logging.getLogger(__name__)


def _score_key(job: dict) -> tuple[float, float]:
    try:
        o = float(job.get("overall_match_score") or 0)
    except (TypeError, ValueError):
        o = 0.0
    try:
        s = float(job.get("skill_match_percentage") or 0)
    except (TypeError, ValueError):
        s = 0.0
    return (o, s)


def _fallback_aggregate(window: list) -> list:
    """Deterministic dedupe by URL + sort by scores when the LLM output is unusable."""
    seen: set[str] = set()
    out: list = []
    for j in window:
        if not isinstance(j, dict):
            continue
        u = str(j.get("url", "")).strip()
        if u:
            if u in seen:
                continue
            seen.add(u)
        out.append(j)
    out.sort(key=_score_key, reverse=True)
    return out


async def aggregate_jobs(profile: dict) -> list:
    """
    Run **Remotive** and **Arbeitnow** matcher agents **in parallel** via ``asyncio.gather`` (same event loop),
    merge results, then pass a slim job window to the aggregator LLM for deduplication and re-ranking.
    """

    remotive_results, arbeitnow_results = await asyncio.gather(
        match_remotive_jobs(profile),
        match_arbeitnow_jobs(profile),
    )

    combined = remotive_results + arbeitnow_results

    if not combined:
        logger.info("Matcher agents returned no jobs; fetching listings directly from APIs.")
        combined = await asyncio.to_thread(fetch_fallback_jobs_sync, profile)
    if not combined:
        return []

    combined_sorted = sorted(
        [j for j in combined if isinstance(j, dict)],
        key=_score_key,
        reverse=True,
    )
    max_jobs = get_aggregator_max_jobs()
    window = combined_sorted[:max_jobs]
    desc_max = get_aggregator_description_max_chars()

    slim: list[dict] = []
    for i, job in enumerate(window):
        desc = str(job.get("description", ""))[:desc_max]
        slim.append(
            {
                "i": i,
                "title": job.get("title"),
                "company": job.get("company") if job.get("company") is not None else job.get("company_name"),
                "url": job.get("url"),
                "source": job.get("source"),
                "overall_match_score": job.get("overall_match_score"),
                "skill_match_percentage": job.get("skill_match_percentage"),
                "description": desc,
            }
        )

    prompt = f"""You deduplicate and rank job matches.

Each item has an integer field `i` (0..{len(window) - 1}), scores, title, company, url, source, and a shortened description.

**Data (JSON):**
{json.dumps(slim, ensure_ascii=False, separators=(",", ":"))}

**Rules:**
1. Deduplicate: same role at the same employer (fuzzy match on title + company, or identical `url`).
2. When duplicates exist, keep the one with higher `overall_match_score`, then `skill_match_percentage`.
3. Order best matches first.

Return **only** a JSON array of integers: the `i` values to keep, in priority order.
Example: [3, 0, 7, 2]
No markdown fences, no extra text.
"""

    agent = Agent(
        name="JobAggregator",
        instructions=prompt,
    )

    result = await Runner.run(
        agent,
        "Return the JSON array of indices now.",
        max_turns=get_agent_max_turns(),
    )

    raw = result.final_output or ""

    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    clean = match.group(1).strip() if match else raw.strip()

    try:
        parsed = json.loads(clean)
    except (TypeError, json.JSONDecodeError):
        logger.info("Aggregator JSON parse failed; using fallback ordering.")
        return _fallback_aggregate(window)

    if isinstance(parsed, list) and parsed and all(isinstance(x, int) for x in parsed):
        ordered: list = []
        seen_i: set[int] = set()
        for idx in parsed:
            if isinstance(idx, int) and 0 <= idx < len(window) and idx not in seen_i:
                seen_i.add(idx)
                ordered.append(window[idx])
        if ordered:
            return ordered
        return _fallback_aggregate(window)

    if isinstance(parsed, list) and parsed and all(isinstance(x, dict) for x in parsed):
        return parsed

    logger.info("Aggregator returned unexpected shape; using fallback ordering.")
    return _fallback_aggregate(window)
