# =============================================
# career_assistant.agents.resume_tailor - LLM tailors CV toward one job
# =============================================

import json

from agents import Agent, Runner

from career_assistant.utils.async_bridge import run_coroutine_sync
from career_assistant.utils.llm_payload import profile_json_for_llm, slim_job_for_tailor
from career_assistant.utils.settings import (
    get_agent_max_turns,
    get_tailor_job_description_max_chars,
    get_tailor_profile_json_max_chars,
)


async def tailor_resume_for_job_async(profile: dict, job: dict) -> str:
    """
    Produce a tailored resume (markdown) emphasizing fit for the given job.

    Does not replace stored profile; output is for copy/download in the UI.
    """

    p_json = profile_json_for_llm(profile, get_tailor_profile_json_max_chars())
    j_slim = slim_job_for_tailor(job, get_tailor_job_description_max_chars())
    j_json = json.dumps(j_slim, ensure_ascii=False, separators=(",", ":"))

    user_message = f"""Candidate profile (JSON):
{p_json}

Target job (JSON):
{j_json}

Produce the tailored Markdown resume now (only the document, no preamble or code fences)."""

    agent = Agent(
        name="ResumeTailor",
        instructions=(
            "You tailor resumes in Markdown for a specific job. "
            "Stay truthful to the profile JSON: do not invent employers, degrees, or skills. "
            "Reorder and emphasize relevance to the job. "
            "Use ## headings (Professional Summary, Experience, Skills, Education). "
            "Professional, concise tone."
        ),
    )

    result = await Runner.run(agent, user_message, max_turns=get_agent_max_turns())
    return (result.final_output or "").strip()


def tailor_resume_for_job(profile: dict, job: dict) -> str:
    """Sync entry for Gradio; delegates to async implementation."""
    return run_coroutine_sync(tailor_resume_for_job_async(profile, job))
