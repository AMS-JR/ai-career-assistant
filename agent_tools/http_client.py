# =============================================
# agent_tools.http_client - pooled HTTP for job APIs
# =============================================

from __future__ import annotations

import atexit

import httpx

from utils.settings import get_http_timeout_seconds

_client: httpx.Client | None = None


def get_job_http_client() -> httpx.Client:
    """Shared sync client (connection pooling) for Arbeitnow / Remotive tools."""
    global _client
    if _client is None:
        timeout = get_http_timeout_seconds()
        _client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
            follow_redirects=True,
        )
    return _client


def _close_job_http_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


atexit.register(_close_job_http_client)
