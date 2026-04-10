# =============================================
# ui.job_ui_utils — shared job list / score helpers
# =============================================

from __future__ import annotations

from typing import Any


def fmt_pct(val: Any) -> str:
    try:
        if val is None or val == "":
            return "—"
        x = float(val)
        if x != x:
            return "—"
        return f"{int(round(x))}%"
    except (TypeError, ValueError):
        return "—"


def _score_pair(job: dict) -> tuple[float, float]:
    def f(x: Any) -> float:
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    return (f(job.get("overall_match_score")), f(job.get("skill_match_percentage")))


def sort_jobs_by_match(jobs: list) -> list[dict]:
    lst = [j for j in jobs if isinstance(j, dict)]
    lst.sort(key=_score_pair, reverse=True)
    return lst
