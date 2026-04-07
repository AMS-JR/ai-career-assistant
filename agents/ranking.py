# =============================================
# agents/ranking.py
# =============================================


def score_job(profile: dict, job: dict) -> int:
    """
    Score job based on skill overlap.
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
    Assign scores to ALL jobs.
    No deduplication here.
    """

    ranked = []

    for job in jobs:
        ranked.append({
            "job": job,
            "score": score_job(profile, job)
        })

    return ranked
