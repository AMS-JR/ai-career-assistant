# =============================================
# agents/ranking.py
# =============================================
from agents import Agent

def score_job(profile: dict, job: dict) -> int:
    """
    Score a single job based on skill overlap.
    """
    skills = profile.get("skills", [])
    if not skills:
        return 0

    score = 0
    job_text = str(job).lower()

    for skill in skills:
        if skill.lower() in job_text:
            score += (100 / len(skills))

    return int(min(score, 100))


def rank_jobs(profile: dict, jobs: list) -> list:
    """
    Rank a list of jobs.
    """
    ranked = []
    for job in jobs:
        ranked.append({
            "job": job,
            "score": score_job(profile, job)
        })
    return ranked


# ✅ Define RankingAgent
RankingAgent = Agent(
    name="RankingAgent",
    instructions="Given a profile and a list of jobs, score each job based on skill overlap and return the scores.",
    run=rank_jobs  # pass the function as the agent's execution logic
)