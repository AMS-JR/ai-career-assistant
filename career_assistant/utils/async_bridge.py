# =============================================
# career_assistant.utils.async_bridge - sync/async boundary
# =============================================

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_coroutine_sync(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an awaitable from synchronous code (e.g. Gradio callbacks).

    Uses ``asyncio.run`` only when no loop is already running, which avoids
    nested ``asyncio.run`` crashes and matches common framework patterns.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError(
        "run_coroutine_sync() cannot be used inside a running event loop; "
        "await the coroutine from async code instead."
    )
