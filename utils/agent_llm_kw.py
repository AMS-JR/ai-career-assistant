# =============================================
# utils.agent_llm_kw — optional Agent(model=...) from env
# =============================================

from __future__ import annotations

from typing import Any

from agents import ModelSettings

from utils.settings import (
    get_agent_model_name,
    get_resume_parser_max_output_tokens,
    get_resume_tailor_max_output_tokens,
)


def agent_kwargs_basic() -> dict[str, Any]:
    """``model`` only when ``OPENAI_*`` model env is set."""
    m = get_agent_model_name()
    return {"model": m} if m else {}


def agent_kwargs_parser() -> dict[str, Any]:
    kw = agent_kwargs_basic()
    cap = get_resume_parser_max_output_tokens()
    if cap is not None:
        kw["model_settings"] = ModelSettings(max_tokens=cap)
    return kw


def agent_kwargs_tailor() -> dict[str, Any]:
    kw = agent_kwargs_basic()
    cap = get_resume_tailor_max_output_tokens()
    if cap is not None:
        kw["model_settings"] = ModelSettings(max_tokens=cap)
    return kw
