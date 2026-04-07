# =============================================
# agents/matcher.py
# =============================================


def match_jobs(profile: dict, jobs: list) -> list:
    """
    Basic keyword filtering based on skills.
    """

    skills = [s.lower() for s in profile.get("skills", [])]
    matched = []

    for job in jobs:
        desc = str(job).lower()
        if any(skill in desc for skill in skills):
            matched.append(job)

    return matched