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
    """Legacy global cap; board matchers prefer :func:`get_matcher_max_turns` (default 14)."""
    v = int(os.getenv("AGENT_MAX_TURNS", "30"))
    return max(10, min(100, v))


def get_resume_parser_max_turns() -> int:
    """Parser has no tools — one JSON object; keep this low to avoid wasted rounds."""
    v = int(os.getenv("RESUME_PARSER_MAX_TURNS", "3"))
    return max(2, min(12, v))


def get_matcher_max_turns() -> int:
    """Remotive/Arbeitnow agents use tools; several calls + final JSON (default 14)."""
    raw = os.getenv("MATCHER_MAX_TURNS", "").strip()
    if raw:
        v = int(raw)
    else:
        v = int(os.getenv("AGENT_MAX_TURNS", "14"))
    return max(4, min(40, v))


def get_job_aggregator_max_turns() -> int:
    """JobAggregator returns a single index array — no tools."""
    v = int(os.getenv("JOB_AGGREGATOR_MAX_TURNS", "3"))
    return max(2, min(12, v))


def get_resume_tailor_max_turns() -> int:
    """Tailor agent: one Markdown document, no tools (single-shot; do not inherit AGENT_MAX_TURNS)."""
    v = int(os.getenv("RESUME_TAILOR_MAX_TURNS", "6"))
    return max(3, min(25, v))


def get_skip_job_aggregator_llm() -> bool:
    """If true, skip the dedupe/rank LLM and use score sort + URL dedupe only (much faster)."""
    return os.getenv("SKIP_JOB_AGGREGATOR_LLM", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_remotive_reconcile_query_cap() -> int:
    """Profile search queries used when building Remotive URL canonical maps (post-agent HTTP)."""
    v = int(os.getenv("REMOTIVE_RECONCILE_QUERY_CAP", "2"))
    return max(1, min(4, v))


def get_agent_model_name() -> str | None:
    """If set, passed to ``Agent(model=...)`` so all career-assistant agents use the same chat model."""
    for key in ("OPENAI_CAREER_MODEL", "OPENAI_DEFAULT_MODEL", "OPENAI_MODEL"):
        v = os.getenv(key, "").strip()
        if v:
            return v
    return None


def get_direct_job_fetch_only() -> bool:
    """
    If true, skip Remotive/Arbeitnow **matcher LLMs** entirely: parallel HTTP fetch + keyword-style
    ranking only (same path as empty-matcher fallback). Fast UI; no LLM scoring on listings.
    """
    return os.getenv("DIRECT_JOB_FETCH_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_arbeitnow_fallback_max_pages() -> int:
    """Pages of Arbeitnow feed to scan in direct/fallback fetch (fewer = faster)."""
    v = int(os.getenv("ARBEITNOW_FALLBACK_MAX_PAGES", "3"))
    return max(1, min(8, v))


def get_resume_parser_max_output_tokens() -> int | None:
    """Optional cap on parser completion size (can speed responses; unset = model default)."""
    raw = os.getenv("RESUME_PARSER_MAX_OUTPUT_TOKENS", "").strip()
    if not raw or raw == "0":
        return None
    return max(1024, min(32000, int(raw)))


def get_resume_tailor_max_output_tokens() -> int | None:
    """Optional cap on tailored resume length (unset = model default)."""
    raw = os.getenv("RESUME_TAILOR_MAX_OUTPUT_TOKENS", "").strip()
    if not raw or raw == "0":
        return None
    return max(1024, min(32000, int(raw)))
