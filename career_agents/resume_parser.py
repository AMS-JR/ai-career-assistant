# =============================================
# agents/resume_parser.py
# =============================================
from email.mime import text
from os import name
from agents import Agent, Runner, Trace
import asyncio
import json


def parse_resume(text: str) -> dict:

    """
     takes in the raw text of a resume and returns a structured profile
      dictionary with keys like name, summary, skills, experience, projects, 
      education, and certifications.
    """

    prompt = f"""
    Given the following resume text, extract the information and
    structure it into a JSON object with the following keys: name, summary, 
    kills, experience, projects, education, and certifications. Only return valid JSON.

        The ouput format should be:

        {{
            "name": "John Doe",
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
    {text}
    """
    agent = Agent(
        name="ResumeParser",
        instructions="You are a resume parser"
    )

    result = asyncio.run(Runner.run(agent, text))

    return json.loads(result.final_output)