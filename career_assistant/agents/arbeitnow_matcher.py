# =============================================
# career_assistant.agents.arbeitnow_matcher
# =============================================

from agents import Agent, Runner

from career_assistant.agent_tools.arbeitnow import fetch_arbeitnow_jobs
from career_assistant.agents.matcher_shared import parse_llm_job_array
from career_assistant.utils.llm_payload import profile_json_for_llm
from career_assistant.utils.settings import (
    get_agent_max_turns,
    get_matcher_min_overall_score,
    get_matcher_min_skill_percent,
    get_matcher_profile_json_max_chars,
)


def _instructions(profile_json: str) -> str:
    ms = get_matcher_min_skill_percent()
    mo = get_matcher_min_overall_score()
    return f"""You are an expert job-matching assistant. You **must** use the **fetch_arbeitnow_jobs** tool to load listings; do not invent jobs.

    **Candidate profile (JSON):**
    {profile_json}

    **Step 1 — Call the Arbeitnow tool (multiple times as needed)**
    The API is **paged** (``page=1``, ``page=2``, …). It does **not** take reliable arbitrary keyword search—use:
    - **page** = 1, then 2, then 3, … for **pagination**. Each page returns a batch; the tool trims to its max. Stale rows (by ``created_at`` unix timestamp) are dropped when older than the configured max age.
    - **remote_only** = true if the candidate clearly wants remote-only and the profile supports that; otherwise false.
    - **require_visa_sponsorship** = true only if the profile explicitly needs visa sponsorship.

    Start with page=1 (and optional filters). If you need more coverage for matching, call again with page=2, page=3, etc.

    **Step 2 — Score each returned job**
    **a) skill_match_percentage (0–100)** — overlap of candidate skills vs job description/tags.
    **b) overall_match_score (0–100)** — ~60% skills, ~20% seniority/title fit, ~15% role alignment, ~5% education; bonuses/penalties.

    **Step 3 — Filtering**
    Prefer skill_match_percentage ≥ {ms} and overall_match_score ≥ {mo}.
    If that removes almost everything, still return the **best matches you have** (do not return an empty array unless every tool call returned no rows).

    **Step 4 — Final answer (no more tool calls)**
    Return **only** a JSON array, sorted by overall_match_score descending. Each object:
    - title, company (from company_name in API rows), location (use location; note if remote is true),
    - description (plain text, max 250 chars), url, source = "Arbeitnow",
    - skill_match_percentage, overall_match_score,
    - matching_skills (array), missing_critical_skills (array), why_this_match (1–2 sentences).

    Optional ```json fence is allowed; no other prose in the final message.
    """


async def match_arbeitnow_jobs(profile: dict) -> list:
    """Agent uses ``fetch_arbeitnow_jobs`` as a tool, then returns scored JSON matches."""
    profile_json = profile_json_for_llm(profile, get_matcher_profile_json_max_chars())
    agent = Agent(
        name="ArbeitnowMatcher",
        instructions=_instructions(profile_json),
        tools=[fetch_arbeitnow_jobs],
    )

    result = await Runner.run(
        agent,
        "Use fetch_arbeitnow_jobs with appropriate page and filter arguments, then return the final JSON array of scored matches.",
        max_turns=get_agent_max_turns(),
    )

    parsed = parse_llm_job_array(result.final_output or "")
    return parsed if parsed is not None else []
