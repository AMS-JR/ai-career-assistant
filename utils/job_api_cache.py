# =============================================
# utils.job_api_cache - short TTL cache for public job APIs
# =============================================

from __future__ import annotations

from collections.abc import Callable
from time import monotonic

_cache: dict[str, tuple[float, list]] = {}


def get_cached_job_list(
    key: str,
    ttl_seconds: float,
    fetch: Callable[[], list],
    *,
    cache_empty: bool = True,
) -> list:
    """Return cached list if fresh; otherwise call ``fetch`` and store.

    If ``cache_empty`` is False, empty lists are not stored (avoids caching transient API failures).
    """
    if ttl_seconds <= 0:
        return fetch()

    now = monotonic()
    hit = _cache.get(key)
    if hit is not None and (now - hit[0]) < ttl_seconds:
        return hit[1]

    data = fetch()
    if not isinstance(data, list):
        data = []
    if not cache_empty and len(data) == 0:
        return data
    _cache[key] = (now, data)
    return data
