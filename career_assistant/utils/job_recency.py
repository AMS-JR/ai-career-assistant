# =============================================
# career_assistant.utils.job_recency - posted-date handling per board
# =============================================

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


def job_posted_unix(raw: dict[str, Any], *, arbeitnow: bool) -> float | None:
    """
    Best-effort posting time as Unix seconds.
    Arbeitnow: ``created_at`` (int/float unix).
    Remotive: ``publication_date`` (ISO string per API docs).
    """
    if arbeitnow:
        ts = raw.get("created_at")
        if isinstance(ts, (int, float)):
            return float(ts)
        return None
    pub = raw.get("publication_date") or raw.get("created_at")
    if isinstance(pub, (int, float)):
        return float(pub)
    if isinstance(pub, str):
        s = pub.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return None
    return None


def filter_raw_jobs_by_recency(
    jobs: list[Any],
    *,
    arbeitnow: bool,
    max_age_days: int,
) -> list[dict[str, Any]]:
    """
    Drop listings older than ``max_age_days`` (0 = no filtering).
    Rows with unknown dates are kept.
    """
    if max_age_days <= 0:
        return [j for j in jobs if isinstance(j, dict)]
    cutoff = time.time() - max_age_days * 86400.0
    out: list[dict[str, Any]] = []
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        ts = job_posted_unix(raw, arbeitnow=arbeitnow)
        if ts is None or ts >= cutoff:
            out.append(raw)
    return out
