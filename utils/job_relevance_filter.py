# =============================================
# utils.job_relevance_filter
# Drop listings with no keyword overlap vs profile title/skills (post-fetch).
# =============================================

from __future__ import annotations

import re
from typing import Any

_STOP = frozenset(
    "the and for with from this that have has been were will your our are was but not you all "
    "can may out day get use new way any who its per via bei und der die das von mit eine auch "
    "sind sich nicht als des zur zum senior junior lead staff principal".split()
)


def profile_keyword_tokens(profile: dict[str, Any]) -> set[str]:
    """Lowercase tokens (len >= 3) from title, skills, summary for loose text match."""
    parts: list[str] = []
    for k in ("title", "headline", "current_role", "summary"):
        v = profile.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)
    sk = profile.get("skills")
    if isinstance(sk, list):
        parts.extend(str(s) for s in sk if s)
    blob = " ".join(parts).lower()
    tokens: set[str] = set()
    for m in re.finditer(r"[a-z0-9][a-z0-9+#.\-]{2,}", blob):
        w = m.group(0).strip(".-")
        if w and w not in _STOP:
            tokens.add(w)
    return tokens


def filter_jobs_by_profile_keywords(
    jobs: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    min_hits: int = 1,
) -> list[dict[str, Any]]:
    """
    Keep jobs whose title or description contains at least ``min_hits`` profile tokens.
    If there are no profile tokens, returns ``jobs`` unchanged.
    """
    tokens = profile_keyword_tokens(profile)
    if not tokens:
        return [j for j in jobs if isinstance(j, dict)]
    out: list[dict[str, Any]] = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        blob = f"{j.get('title', '')} {j.get('description', '')}".lower()
        hits = sum(1 for t in tokens if t in blob)
        if hits >= min_hits:
            out.append(j)
    return out
