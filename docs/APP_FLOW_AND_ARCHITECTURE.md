# AI Career Assistant — Architecture, Flow, and Agentic Design

**Document type:** Technical architecture and operations reference.  
**Editable source:** This Markdown file. **PDF:** Regenerate with `uv run python scripts/gen_architecture_pdf.py` from the repository root (ReportLab; no LaTeX required).

**Last aligned with codebase:** April 2026.

---

## Document scope

This document explains how the AI Career Assistant is structured, how data moves through the system, how **OpenAI Agents SDK** agents and tools cooperate, and what tradeoffs affect **quality, latency, and cost**. It is intended for developers, reviewers, and anyone extending the pipeline.

---

## 1. Purpose and capabilities

The application supports a single candidate session:

1. **Ingest** a resume (PDF or Word), extract **structured profile** JSON via an LLM.
2. **Search** remote job boards (**Remotive**, **Arbeitnow**) using agent-driven matching that scores listings against the profile.
3. **Aggregate** merged results with a second LLM pass for deduplication and ranking.
4. **Tailor** a **Markdown resume** to one selected posting while staying faithful to extracted facts; the UI can render a **PDF** download from that Markdown.

Optional hooks sync parsed content to an **OpenAI vector store** when `PROFILE_BACKEND=openai_vector_store`, enabling future RAG workflows without changing the core matching path.

**Primary stack:** Python 3.12+, **Gradio 6** (UI), **OpenAI Agents SDK** (`agents.Agent`, `agents.Runner`), **httpx** (shared HTTP for job APIs), **ReportLab** (PDF export in the UI layer).

**Entry point:** `career-assistant` CLI → `career_assistant.main:main` → `career_assistant.ui.app.run_app()` → `demo.launch(...)` with theme and `css_paths` pointing at `career_assistant/ui/app.css`.

---

## 2. Layered system architecture

The system splits into five logical layers. Upper layers depend on lower ones; job tools and HTTP sit at the bottom.

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation (Gradio 6)                                     │
│  app.py, render_html.py, job_ui_utils.py, app.css            │
├─────────────────────────────────────────────────────────────┤
│  Workflow orchestration (thin)                               │
│  orchestrator.py — parse + match facades, async_bridge        │
├─────────────────────────────────────────────────────────────┤
│  Agents (LLM reasoning + optional tools)                       │
│  resume_parser, remotive_matcher, arbeitnow_matcher,          │
│  aggregator (JobAggregator), resume_tailor, job_fallback     │
├─────────────────────────────────────────────────────────────┤
│  Tools & integrations                                        │
│  agent_tools.remotive, agent_tools.arbeitnow, http_client      │
├─────────────────────────────────────────────────────────────┤
│  Cross-cutting utilities                                       │
│  settings, documents, llm_payload, job_api_cache, job_recency, │
│  job_relevance_filter, profile_storage, async_bridge           │
└─────────────────────────────────────────────────────────────┘
```

**Presentation layer** owns session state (`gr.State`), generator-based progress updates to a custom HTML status bar, HTML templates under `ui/html/`, and PDF generation for tailored output.

**Orchestration** exposes synchronous entry points the UI calls (`parse_resume_from_text`, `run_matching_for_profile`) by running async agent code on a single event loop via `run_coroutine_sync`.

**Agents** encapsulate prompts and (for matchers) **declared tools** the model can invoke. **Runner.run** executes each agent with a configurable **max_turns**.

**Tools** perform deterministic work: HTTP GET to public job APIs, normalization, caching, and recency filtering before text is returned to the model.

---

## 3. End-to-end user flow (Gradio)

### 3.1 Step 1 — Resume and profile

- User selects a `.pdf`, `.docx`, or `.doc` file.
- **Extract profile** triggers a chain: text extraction (`utils.documents.extract_resume_text`), then `parse_resume_from_text` → `resume_parser.parse_resume_async`.
- The resulting **profile dict** is stored in session state. The profile panel re-renders from `render_html.profile_html`.
- If configured, `profile_storage.sync_resume_to_vector_store` uploads raw text / metadata for vector-store backends.

**Progress UX:** Generators `yield` updates to `gr.HTML` status (`status_busy_html`) with optional percent; `show_progress="hidden"` and CSS suppress Gradio’s default queue bar.

### 3.2 Step 2 — Job search

- **Search jobs** calls `run_matching_for_profile` → `aggregate_jobs`.
- The UI sorts with `job_ui_utils.sort_jobs_by_match`, then applies `filter_jobs_by_profile_keywords`. If that removes every job, behavior depends on `RELAX_PROFILE_KEYWORD_JOB_FILTER` (relax vs empty state with `keyword_filter_no_results`).
- Results render as HTML job cards (`jobs_html` / `job_card.html`); the dropdown uses the same ordering.

### 3.3 Step 3 — Tailored application

- User selects a posting index, then **Generate tailored PDF**.
- `tailor_resume_for_job` returns Markdown; the UI shows it in `gr.Markdown` and builds a **PDF** with `_write_tailored_pdf` (ReportLab) for `gr.DownloadButton` when possible.

### 3.4 Session state (conceptual)

| Key | Role |
|-----|------|
| `profile` | Parsed resume JSON or `None` |
| `jobs` | List of job dicts from last successful search |
| `job_search_ran` | Whether search has run at least once |
| `keyword_filter_no_results` | Keyword filter eliminated all matches |

**Clear session** resets profile, jobs, and UI placeholders.

---

## 4. Backend pipeline — job matching (detailed)

### 4.1 Parallel matchers

`aggregate_jobs` (`agents/aggregator.py`) runs **in parallel**:

- `match_remotive_jobs(profile)`
- `match_arbeitnow_jobs(profile)`

via `asyncio.gather` in the **same** event loop as the rest of the async agents.

Results are concatenated. If both are empty, **`fetch_fallback_jobs_sync`** pulls listings directly from APIs (deterministic path) and still produces scored-style structures for downstream steps.

### 4.2 Pre-sort and slim window

Combined jobs are filtered to dicts, sorted by **`(overall_match_score, skill_match_percentage)`** descending, then truncated to **`AGGREGATOR_MAX_JOBS`** (default floor 5). For each retained job, descriptions are truncated to **`AGGREGATOR_DESCRIPTION_MAX_CHARS`** for the aggregator prompt.

### 4.3 JobAggregator agent

A dedicated **Agent** (no tools) receives JSON with integer indices `i`, scores, titles, companies, URLs, sources, and short descriptions. It must return **only** a JSON array of indices in priority order (deduplicate fuzzy duplicates, prefer higher scores).

**Robustness:** If parsing fails or the shape is wrong, **`_fallback_aggregate`** deduplicates by URL and sorts by score deterministically.

### 4.4 Remotive matcher (agent + tools + reconciliation)

- The matcher agent is instructed to call **`fetch_remotive_jobs`** (tool) so listings come from live API data.
- Parsed LLM output is normalized through **`matcher_shared.parse_llm_job_array`**.
- **URL reconciliation:** Remotive listing URLs are sensitive to slug shape; the matcher builds a **canonical map** from API rows (by numeric `id` and by normalized `(title, company)`) and rewrites model-supplied URLs to reduce **404s** from shortened or hallucinated links.

### 4.5 Arbeitnow matcher

Same pattern: tool **`fetch_arbeitnow_jobs`**, trimmed payloads via **`llm_payload.trim_api_jobs_for_llm`** with EU-oriented shaping, shared parsing and score thresholds from settings.

### 4.6 HTTP, cache, and recency

- **`agent_tools.http_client`:** Shared client; timeout from **`JOB_HTTP_TIMEOUT_SECONDS`**.
- **`job_api_cache`:** Short TTL cache for GET responses (**`JOB_API_CACHE_TTL_SECONDS`**; `0` disables).
- **`job_recency`:** Optional drop of stale listings using **`JOB_LISTING_MAX_AGE_DAYS`**.

---

## 5. Resume parsing and tailoring agents

### 5.1 Resume parser

- **Input:** Plain text (truncated to **`RESUME_PARSE_MAX_INPUT_CHARS`**).
- **Output:** JSON object with fields such as `name`, `title`, `years_of_experience`, `summary`, `skills`, `experience`, `projects`, `education`, `certifications`.
- **Agent:** `Agent` + `Runner.run` with **`get_agent_max_turns()`**; output is parsed with **`_parse_json_object_from_llm`** (tolerates markdown fences and trailing prose).

### 5.2 Resume tailor

- **Input:** Slim profile JSON (`profile_json_for_llm`) and slim job JSON (`slim_job_for_tailor`), both size-capped by settings.
- **Output:** Markdown resume (no invented employers, degrees, or skills per instructions).
- **UI:** Markdown preview + optional PDF via ReportLab layout logic in `ui/app.py`.

---

## 6. How the agentic app works (conceptual model)

1. **Agent = policy + instructions.** Each agent has a name, system-style instructions (and for matchers, access to **tools**).
2. **Runner = execution engine.** `Runner.run(agent, input, max_turns=...)` lets the model reason, call tools (when defined), and return **`final_output`** as text.
3. **Tools = ground truth for listings.** Matchers are steered to fetch jobs through tools so URLs and titles align with API responses; reconciliation fixes remaining drift.
4. **Two-stage matching.** Per-board agents score broadly; **JobAggregator** focuses on **dedupe and ordering** over a bounded window to control tokens.
5. **Sync bridge for UI.** Gradio handlers are synchronous; **`async_bridge.run_coroutine_sync`** runs coroutines without requiring an async Gradio handler everywhere.

This is **not** a multi-agent debate loop: agents are **sequential stages** (parse → match boards in parallel → aggregate → tailor on demand), which keeps behavior predictable and easier to test.

---

## 7. Data shapes (informal contract)

**Profile (parsed):** Dict with string/list/numeric fields; `skills` is often a list of strings (the UI may split comma-separated blobs into chips).

**Job (matched):** Dict including at least `title`, `company` / `company_name`, `url`, `description`, scoring fields (`overall_match_score`, `skill_match_percentage`), `source`, and when available **`id`** (important for Remotive reconciliation).

---

## 8. Tradeoffs and design decisions

| Decision | Benefit | Cost / risk |
|----------|---------|-------------|
| LLM for parsing | Handles varied resume layouts | Cost, occasional JSON repair; truncation may drop tail content |
| LLM matchers + tools | Flexible scoring language; tools anchor listings | Latency (two board agents + aggregator); model variance |
| Aggregator window cap | Bounded prompt size, predictable cost | Jobs beyond the window cannot be reordered by aggregator |
| Keyword filter post-pass | Surfaces keyword-relevant roles | May empty results; mitigated by relax flag |
| Remotive URL reconciliation | Fewer broken links | Extra API-aligned fetches when building canonical maps |
| `max_turns` limits | Prevents runaway tool loops | Complex tasks may truncate early if set too low |
| Session-only profile default | Simple privacy story | No server-side persistence unless vector store enabled |

---

## 9. Performance characteristics

- **Parallelism:** Remotive and Arbeitnow matchers run concurrently; wall-clock for matching is roughly **max(board A, board B)** plus aggregator time, not the sum of both.
- **Caching:** Repeated searches within TTL reuse HTTP responses, reducing API load and latency.
- **Truncation:** Resume text, job descriptions, profile JSON in prompts, and aggregator window all cap tokens—**latency and cost scale sublinearly** with raw data size but may **lose tail detail**.
- **UI progress:** Coarse-grained yields (a few steps per operation) limit Gradio update overhead while still signaling state.
- **PDF generation:** CPU-bound ReportLab work runs in the request path for tailoring; large Markdown could increase time to first download.

**Bottlenecks (typical):** OpenAI API latency for parser, two matchers, aggregator, and tailor; network to Remotive/Arbeitnow when cache misses.

---

## 10. Configuration reference

Centralized in **`career_assistant.utils.settings`** (environment variables; see `.env` patterns in repo).

| Area | Examples |
|------|----------|
| Profile / RAG | `PROFILE_BACKEND`, `OPENAI_VECTOR_STORE_ID` |
| HTTP / listings | `JOB_HTTP_TIMEOUT_SECONDS`, `JOB_API_CACHE_TTL_SECONDS`, `JOB_LISTING_MAX_AGE_DAYS` |
| Tool payloads | `JOB_TOOL_MAX_RESULTS`, `JOB_TOOL_DESCRIPTION_MAX_CHARS`, `MATCHER_PROFILE_JSON_MAX_CHARS` |
| Matcher thresholds | `MATCHER_MIN_OVERALL_SCORE`, `MATCHER_MIN_SKILL_PERCENT` (as implemented in settings) |
| Agents | `AGENT_MAX_TURNS` |
| Aggregator | `AGGREGATOR_MAX_JOBS`, `AGGREGATOR_DESCRIPTION_MAX_CHARS` |
| Parser / tailor | `RESUME_PARSE_MAX_INPUT_CHARS`, `TAILOR_PROFILE_JSON_MAX_CHARS`, `TAILOR_JOB_DESCRIPTION_MAX_CHARS` |
| UI filter | `RELAX_PROFILE_KEYWORD_JOB_FILTER` |

---

## 11. Package layout (reference)

```
career_assistant/
  main.py                 # CLI entry, logging, load_dotenv
  agent_tools/            # remotive, arbeitnow, http_client
  agents/                 # orchestrator, aggregator, matchers, resume_parser,
                          # resume_tailor, job_fallback, matcher_shared
  utils/                  # settings, documents, profile_storage, llm_payload,
                          # job_api_cache, job_recency, job_relevance_filter, async_bridge, …
  ui/
    app.py                # Gradio Blocks, events, PDF helper, launch(css_paths=…)
    app.css               # Custom theme (loaded via launch, not Blocks)
    render_html.py        # HTML fragments, profile/jobs/status templates
    html/                 # Small HTML templates
    job_ui_utils.py       # Sorting, dropdown choices, display helpers
```

---

## 12. Regenerating the PDF

From the repository root:

```bash
uv run python scripts/gen_architecture_pdf.py
```

Requires **reportlab** (declared in project dependencies). Output: **`docs/APP_FLOW_AND_ARCHITECTURE.pdf`**.

Alternative: Pandoc with a PDF engine (e.g. LaTeX), if you prefer a different typographic pipeline:

```bash
pandoc docs/APP_FLOW_AND_ARCHITECTURE.md -o docs/APP_FLOW_AND_ARCHITECTURE.pdf
```

---

*End of document.*
