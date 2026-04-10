# AI CAREER ASSISTANT - COMPLETE STARTER (WITH AGGREGATOR)

Modular, team-friendly baseline using OpenAI + Gradio

Each section below should be split into its own file as indicated.

# Collaborators

[AMS-JR](https://github.com/AMS-JR)
[Jones Omoyibo](https://github.com/Benklins)
[Williams Afotey Botchway](https://github.com/wafotey)

# PROJECT STRUCTURE

Python code lives in the **`career_assistant`** package (installable via `uv sync` / `pip install -e .`).

```
project/
|-- main.py                      # thin shim -> career_assistant.main
|-- career_assistant/
|   |-- main.py                  # `python -m career_assistant.main` entry
|   |-- agent_tools/             # @function_tool job-board HTTP helpers
|   |   |-- arbeitnow.py
|   |   `-- remotive.py
|   |-- agents/
|   |   |-- orchestrator.py      # parse + match pipeline
|   |   |-- resume_parser.py
|   |   |-- resume_tailor.py
|   |   |-- arbeitnow_matcher.py
|   |   |-- remotive_matcher.py
|   |   `-- aggregator.py
|   |-- utils/
|   |   |-- async_bridge.py      # run_coroutine_sync (Gradio / asyncio)
|   |   |-- settings.py          # env: PROFILE_BACKEND, vector store id
|   |   |-- profile_storage.py   # local vs vector-store hooks
|   |   `-- documents.py         # .pdf / .docx / .doc text extraction
|   `-- ui/
|       `-- app.py
|-- data/
|   `-- resume.pdf
`-- pyproject.toml
```

The **`openai-agents`** library is imported as **`from agents import ...`**. Local workflows live under **`career_assistant.agents`** so they stay separate from that package.

# INSTALLATION (UV)

- `uv sync` (creates `.venv` and installs the project + dependencies from `pyproject.toml`)
- `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)

If you install manually instead: `uv pip install openai gradio python-dotenv pypdf python-docx` (see `pyproject.toml` for the full list).

**Resume uploads:** `.pdf` and `.docx` work out of the box. Legacy **`.doc`** needs the **`antiword`** binary on your PATH (e.g. `brew install antiword`), or convert to PDF/DOCX.

**Profile storage (env):** Copy `.env.example` to `.env`. Set `PROFILE_BACKEND=local` (default) to keep parsed profiles only in Gradio session state. Set `PROFILE_BACKEND=openai_vector_store` and `OPENAI_VECTOR_STORE_ID` when you wire RAG (`career_assistant/utils/profile_storage.py` hooks). Until then, the UI still uses session state and may show a configuration note.

**Run:** `uv run python -m career_assistant.main` or `uv run python main.py` from the repo root.

# TEAM NOTES

- Resume Parser -> improve JSON reliability
- Matcher -> improve filtering (LLM or embeddings later)
- Aggregator -> dedupe + re-rank
- UI -> Gradio Blocks: upload/parse once (session state), job cards with apply links, per-job resume tailoring agent
- Future -> memory, RAG, saved profiles (vectors optional)
