# =============================================
# career_assistant.utils.settings - env-driven configuration
# =============================================

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of career_assistant package (.../career_assistant/utils, up 2)
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()


class ProfileBackend(str, Enum):
    """Where parsed resume data is anchored for the session / RAG extensions."""

    LOCAL = "local"
    """In-browser `gr.State` only (default). No OpenAI Files / vector store."""

    OPENAI_VECTOR_STORE = "openai_vector_store"
    """Use OpenAI vector store for file-backed RAG (see `utils.profile_storage` hooks)."""


def get_profile_backend() -> ProfileBackend:
    raw = os.getenv("PROFILE_BACKEND", "local").lower().strip()
    for member in ProfileBackend:
        if member.value == raw:
            return member
    return ProfileBackend.LOCAL


def get_openai_vector_store_id() -> str | None:
    vid = os.getenv("OPENAI_VECTOR_STORE_ID", "").strip()
    return vid or None


def get_http_timeout_seconds() -> float:
    return float(os.getenv("JOB_HTTP_TIMEOUT_SECONDS", "15"))


def get_job_api_cache_ttl_seconds() -> float:
    """0 disables caching for job-board HTTP responses."""
    return float(os.getenv("JOB_API_CACHE_TTL_SECONDS", "300"))


def get_job_listing_max_age_days() -> int:
    """Drop listings older than this many days (0 = keep all). See ``job_recency.job_posted_unix``."""
    v = int(os.getenv("JOB_LISTING_MAX_AGE_DAYS", "90"))
    return max(0, min(365, v))


def get_relax_profile_keyword_job_filter() -> bool:
    """If true, when keyword overlap filter removes all jobs, keep the unfiltered list instead of showing none."""
    return os.getenv("RELAX_PROFILE_KEYWORD_JOB_FILTER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_aggregator_max_jobs() -> int:
    """Max jobs passed to the aggregator LLM (after score pre-sort)."""
    return max(5, int(os.getenv("AGGREGATOR_MAX_JOBS", "40")))


def get_aggregator_description_max_chars() -> int:
    """Truncate descriptions in the slim payload sent to the aggregator."""
    return max(80, int(os.getenv("AGGREGATOR_DESCRIPTION_MAX_CHARS", "400")))


def get_resume_parse_max_input_chars() -> int:
    """Max characters of raw resume text sent to the parser LLM (avoids context overflow)."""
    return max(4000, int(os.getenv("RESUME_PARSE_MAX_INPUT_CHARS", "24000")))


def get_job_tool_max_results() -> int:
    """Max jobs returned per tool call to the matcher (each description is capped separately)."""
    return max(5, min(80, int(os.getenv("JOB_TOOL_MAX_RESULTS", "20"))))


def get_job_tool_description_max_chars() -> int:
    """Plain-text description length cap per job in tool results."""
    return max(200, int(os.getenv("JOB_TOOL_DESCRIPTION_MAX_CHARS", "800")))


def get_matcher_profile_json_max_chars() -> int:
    """Upper bound on candidate profile JSON size embedded in matcher instructions."""
    return max(2000, int(os.getenv("MATCHER_PROFILE_JSON_MAX_CHARS", "14000")))


def get_tailor_profile_json_max_chars() -> int:
    return max(2000, int(os.getenv("TAILOR_PROFILE_JSON_MAX_CHARS", "18000")))


def get_tailor_job_description_max_chars() -> int:
    return max(200, int(os.getenv("TAILOR_JOB_DESCRIPTION_MAX_CHARS", "2500")))


def get_matcher_min_skill_percent() -> int:
    """Minimum skill-match % for a job to be included (LLM filter in matcher prompts)."""
    v = int(os.getenv("MATCHER_MIN_SKILL_PERCENT", "50"))
    return max(25, min(95, v))


def get_matcher_min_overall_score() -> int:
    """Minimum overall match score (0-100) for inclusion."""
    v = int(os.getenv("MATCHER_MIN_OVERALL_SCORE", "50"))
    return max(25, min(100, v))


def get_agent_max_turns() -> int:
    """Max LLM↔tool turns per ``Runner.run`` (SDK default 10 is often too low for matchers)."""
    v = int(os.getenv("AGENT_MAX_TURNS", "30"))
    return max(10, min(100, v))
