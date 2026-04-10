# =============================================
# utils.profile_storage - local vs vector-store strategy
# =============================================

"""
`PROFILE_BACKEND=local` (default) matches the current UI: parsed profile lives in `gr.State`.

`PROFILE_BACKEND=openai_vector_store` is for when you want resume (or chunks) in an OpenAI
vector store for retrieval / Assistants RAG. The hooks below are the extension points;
wire them to the OpenAI Files + vector store APIs when you are ready.

Until implemented, the UI still uses `gr.State`; misconfiguration only produces warnings.
"""

from __future__ import annotations

from typing import Any

from utils.settings import (
    ProfileBackend,
    get_openai_vector_store_id,
    get_profile_backend,
)


def validate_profile_backend() -> list[str]:
    """Human-readable issues (shown in UI); empty if OK."""
    out: list[str] = []
    if get_profile_backend() == ProfileBackend.OPENAI_VECTOR_STORE:
        if not get_openai_vector_store_id():
            out.append(
                "`OPENAI_VECTOR_STORE_ID` is not set - vector mode is not active; "
                "the app keeps using in-memory session state only."
            )
    return out


def describe_profile_backend_line() -> str:
    mode = get_profile_backend().value
    vid = get_openai_vector_store_id()
    if mode == ProfileBackend.OPENAI_VECTOR_STORE.value and vid:
        return f"Profile backend: **`{mode}`** | vector store id `{vid[:8]}...` (RAG hooks optional)."
    return f"Profile backend: **`{mode}`** | parsed profile kept in browser session (`gr.State`)."


def sync_resume_to_vector_store(
    *,
    profile: dict[str, Any],
    raw_text: str | None = None,
    filename: str | None = None,
) -> None:
    """
    Future: upload `raw_text` or serialized profile to Files API and attach to
    `OPENAI_VECTOR_STORE_ID` for semantic search / tailoring with file_search.

    No-op unless backend is `openai_vector_store` and store id is configured.
    """
    if get_profile_backend() != ProfileBackend.OPENAI_VECTOR_STORE:
        return
    if not get_openai_vector_store_id():
        return
    # TODO: OpenAI client - files.create + vector_stores.file_batches or Assistants API
    _ = (profile, raw_text, filename)
