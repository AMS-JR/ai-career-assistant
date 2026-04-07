# =============================================
# AI CAREER ASSISTANT - COMPLETE STARTER (WITH AGGREGATOR)
# =============================================
# Modular, team-friendly baseline using OpenAI + Gradio
# Each section below should be split into its own file as indicated.

# =============================================
# PROJECT STRUCTURE
# =============================================
# project/
# ├── main.py
# ├── orchestrator.py
# │
# ├── agents/
# │   ├── resume_parser.py
# │   ├── matcher.py
# │   ├── ranking.py
# │   ├── aggregator.py
# │   ├── resume_generator.py
# │
# ├── apis/
# │   ├── remotive.py
# │   ├── arbeitnow.py
# │
# ├── utils/
# │   ├── pdf_reader.py
# │
# ├── data/
# │   ├── resume.pdf
# │
# ├── ui/
# │   ├── gradio_app.py

# =============================================
# INSTALLATION (UV)
# =============================================
# uv venv
# source .venv/bin/activate   (Windows: .venv\Scripts\activate)
# uv pip install openai gradio requests python-dotenv PyPDF2

# =============================================
# TEAM NOTES
# =============================================
# - Resume Parser → improve JSON reliability
# - Matcher → improve filtering (LLM or embeddings later)
# - Ranking → refine scoring weights
# - Aggregator → already clean and modular
# - UI → add buttons (Apply / Generate Resume)
# - Future → add memory, RAG, email notifications

# This version strictly follows your architecture with a separate Aggregator Agent.
