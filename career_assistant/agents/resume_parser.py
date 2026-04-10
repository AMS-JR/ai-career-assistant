# =============================================
# career_assistant.agents.resume_parser
# =============================================

import json
import re

from agents import Agent, Runner

from career_assistant.utils.async_bridge import run_coroutine_sync
from career_assistant.utils.llm_payload import truncate_chars
from career_assistant.utils.settings import get_agent_max_turns, get_resume_parse_max_input_chars


def _parse_json_object_from_llm(raw: str) -> dict:
    """Parse a JSON object from model output; tolerate ```json fences and leading prose."""
    s = (raw or "").strip()
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
    if fence:
        try:
            out = json.loads(fence.group(1).strip())
            return out if isinstance(out, dict) else {}
        except json.JSONDecodeError:
            pass
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        try:
            out = json.loads(s[start : end + 1])
            return out if isinstance(out, dict) else {}
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("Expected a JSON object in model output", s, 0)


async def parse_resume_async(text: str) -> dict:
    """
    Parse raw resume text into a structured profile dict
    (name, title, years_of_experience, summary, skills, experience, projects, education, certifications).
    """

    max_in = get_resume_parse_max_input_chars()
    body = truncate_chars(text or "", max_in)
    truncated_note = ""
    if text and len(text) > max_in:
        truncated_note = f"\n\n[Note: resume text was truncated to {max_in} characters for processing.]\n"

    prompt = f"""
    Given the following resume text, extract the information and
    structure it into a JSON object with the following keys: name, title,
    years_of_experience, summary, skills, experience, projects, education, and certifications.
    Only return valid JSON.

    - title: current or target professional headline exactly as on the resume (e.g. "Senior Software Engineer").
    - years_of_experience: total years in the workforce in this field as a number (e.g. 6) or string if uncertain (e.g. "5+").

        The output format should be:

        {{
            "name": "John Doe",
            "title": "Senior Software Engineer",
            "years_of_experience": 6,
            "summary": "Experienced software engineer with a passion for developing innovative programs that expedite the efficiency and effectiveness of organizational success.",
            "skills": ["Python", "Machine Learning", "Data Analysis"],
            "experience": [
                {{
                    "company": "Tech Company",
                    "role": "Software Engineer",
                    "duration": "Jan 2020 - Present",
                    "description": "Worked on developing scalable web applications."
                }}
            ],
            "projects": [
                {{
                    "name": "Project Alpha",
                    "description": "A machine learning project that predicts customer churn."
                }}
            ],
            "education": [
                {{
                    "institution": "University of Technology",
                    "degree": "B.Sc. in Computer Science",
                    "year": 2019
                }}
            ],
            "certifications": [
                {{
                    "name": "Certified Python Developer",
                    "issuer": "Python Institute",
                    "year": 2021
                }}
            ]
        }}
    Resume:
    {body}{truncated_note}
    """
    agent = Agent(
        name="ResumeParser",
        instructions=(
            "You are a resume parser. Follow the user message exactly. "
            "Respond with one JSON object only: keys name, title, years_of_experience, summary, skills, experience, "
            "projects, education, certifications. Use [] or null for missing sections. "
            "No markdown fences, no explanation before or after the JSON."
        ),
    )

    result = await Runner.run(agent, prompt, max_turns=get_agent_max_turns())
    return _parse_json_object_from_llm(result.final_output or "")


def parse_resume(text: str) -> dict:
    """Sync entry for scripts; delegates to ``parse_resume_async`` via ``asyncio.run``."""
    return run_coroutine_sync(parse_resume_async(text))
