# =============================================
# agents/resume_parser.py
# =============================================
from openai import OpenAI
import json

client = OpenAI()


def parse_resume(text: str) -> dict:
    """
    Extract structured profile from resume.
    """

    prompt = f"""
    Extract structured JSON from this resume.
    Keys: name, summary, skills, experience, projects, education, certifications.
    Only return valid JSON.

    Resume:
    {text}
    """

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    try:
        return json.loads(response.output_text)
    except:
        return {"skills": [], "error": "Parsing failed"}
