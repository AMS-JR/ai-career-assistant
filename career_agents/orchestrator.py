# =============================================
# career_agents.orchestrator - end-to-end workflow
# =============================================

import asyncio
import json

from career_agents.aggregator import aggregate_jobs
from career_agents.resume_parser import parse_resume_async
from utils.async_bridge import run_coroutine_sync

DEFAULT_RESUME_PDF = "data/resume.pdf"


async def parse_resume_from_text_async(text: str) -> dict | None:
    """Parse raw resume text; returns None on failure or non-dict payload."""
    try:
        profile = await parse_resume_async(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return profile if isinstance(profile, dict) else None


def parse_resume_from_text(text: str) -> dict | None:
    """Sync entry for UI and scripts."""
    return run_coroutine_sync(parse_resume_from_text_async(text))


async def run_matching_for_profile_async(profile: dict) -> list:
    """Match and aggregate jobs (async)."""
    return await aggregate_jobs(profile)


def run_matching_for_profile(profile: dict) -> list:
    """Sync entry for UI."""
    return run_coroutine_sync(run_matching_for_profile_async(profile))


async def run_pipeline_async() -> list:
    """Full pipeline: default file -> text -> profile -> matches (single event-loop run)."""
    from utils.documents import extract_resume_text

    text = await asyncio.to_thread(extract_resume_text, DEFAULT_RESUME_PDF)
    profile = await parse_resume_from_text_async(text)
    if profile is None:
        return []
    return await aggregate_jobs(profile)


def run_pipeline() -> list:
    """Backward-compatible sync entry for scripts/tests."""
    return run_coroutine_sync(run_pipeline_async())
