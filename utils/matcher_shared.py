# =============================================
# career_agents.matcher_shared - parse matcher LLM JSON output
# =============================================

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_llm_job_array(raw: str) -> list[dict[str, Any]] | None:
    """Extract a JSON array from model output."""
    if not raw or not raw.strip():
        return None
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    clean = match.group(1).strip() if match else raw.strip()
    try:
        parsed = json.loads(clean)
    except (TypeError, json.JSONDecodeError):
        logger.info("Matcher LLM output was not valid JSON.")
        return None
    if not isinstance(parsed, list):
        return None
    return [x for x in parsed if isinstance(x, dict)]
