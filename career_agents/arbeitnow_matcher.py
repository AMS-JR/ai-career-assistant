# agents/matcher_arbeitnow.py
# =============================================

import json
import re

from agents import Agent, Runner
from apis.arbeitnow import fetch_arbeitnow_jobs


async def match_arbeitnow_jobs(profile: dict) -> list:
    """
    Use an agent + Arbeitnow tool to return high-quality job matches.
    """

    prompt = """You are an expert AI job matching assistant.

    **Candidate Profile (structured JSON):**
    {candidate_profile}

    **Task:**
    1. Fetch active job listings from Arbeitnow using the public API:
    - Endpoint: https://www.arbeitnow.com/api/job-board-api
    - Use the Arbeitnow tool with a `search` keyword derived from the candidate's profile.
    - Run 2-3 searches with different relevant keywords to maximize coverage
        (e.g. "python backend", "django developer", "software engineer").
    - Jobs are returned inside a `"data"` array. Each job has these fields:
        - `title`
        - `company_name`
        - `location`
        - `remote` (boolean — true/false)
        - `tags` (list of skill/category tags)
        - `job_types` (list e.g. ["Full-time", "professional / experienced"])
        - `description` (HTML string — parse it as plain text for matching)
        - `url` (direct job link)
        - `created_at` (unix timestamp)

    2. For each job, calculate **two separate metrics**:

    **a) Skill Match Percentage (0-100%)**
        - Purely based on the candidate's skills vs. skills/tools/technologies
            mentioned in the job description, tags, or requirements.
        - Count how many of the candidate's skills appear (exact or strong semantic match).
        - Formula: (Number of matched skills / Total candidate skills) × 100
        - Prioritize hard/technical skills.

    **b) Overall Match Score (0-100)**
        - Holistic score combining:
            - Skill Match Percentage (60% weight)
            - Experience & Seniority Fit (20% weight)
            - Role & Responsibility Alignment (15% weight)
            - Education/Certification relevance (5% weight)

    - Add **bonus points** (max +10): Strong tool overlap, tag alignment, nice-to-have skills covered.
    - Apply **penalties** (max -15): Missing critical/must-have skills, major seniority mismatch.

    3. **Filtering Rule**: Only include jobs where **Skill Match Percentage ≥ 70%** AND **Overall Match Score ≥ 70**.

    4. For each qualifying job, output a dictionary with these keys:

    - `title`
    - `company`               ← use `company_name` from the API
    - `location`              ← use `location` field, or "Fully Remote" if `remote` is true
    - `description`           ← concise plain-text summary, max 250 characters
    - `url`
    - `source`                ← always set to "Arbeitnow"
    - `skill_match_percentage`
    - `overall_match_score`
    - `matching_skills`       (list)
    - `missing_critical_skills` (list, if any)
    - `why_this_match`        (1-2 sentence explanation)

    5. Return the final result as a **valid JSON array**, sorted by `overall_match_score` descending (highest first).

    Example output structure:
    ```json
    [
        {
        "title": "Senior Python Backend Engineer",
        "company": "Stripe",
        "location": "Fully Remote",
        "description": "Build scalable payment systems using Python and Django...",
        "url": "https://www.arbeitnow.com/jobs/companies/stripe/senior-python-backend-engineer-123456",
        "source": "Arbeitnow",
        "skill_match_percentage": 85,
        "overall_match_score": 92,
        "matching_skills": ["Python", "Django", "AWS", "PostgreSQL", "Git"],
        "missing_critical_skills": ["Kubernetes"],
        "why_this_match": "Very strong skill coverage (85%) with excellent alignment to 6+ years of backend experience."
        }
    ]
    ```
    """

    agent = Agent(
        name="ArbeitnowMatcher",
        instructions=prompt.replace("{candidate_profile}", json.dumps(profile, indent=2)),
        tools=[fetch_arbeitnow_jobs],
    )

    result = await Runner.run(agent, "Find and match jobs for this candidate.")

    raw = result.final_output or ""

    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    clean = match.group(1).strip() if match else raw.strip()

    try:
        parsed = json.loads(clean)
    except (TypeError, json.JSONDecodeError):
        return []

    return parsed if isinstance(parsed, list) else []