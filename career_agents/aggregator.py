# =============================================
# agents/aggregator.py
# =============================================
from agents import Agent

def aggregate_jobs(ranked_jobs: list, top_n: int = 10) -> list:
    """
    Aggregator logic:
    - Remove duplicates (based on job id or title)
    - Sort by score descending
    - Return top N
    """
    seen = set()
    unique_jobs = []

    for item in ranked_jobs:
        job_id = item["job"].get("id") or item["job"].get("title")
        if job_id not in seen:
            seen.add(job_id)
            unique_jobs.append(item)

    # Sort descending by score
    sorted_jobs = sorted(unique_jobs, key=lambda x: x["score"], reverse=True)

    # Return top N
    return sorted_jobs[:top_n]


# ✅ Define AggregatorAgent
AggregatorAgent = Agent(
    name="AggregatorAgent",
    instructions="remove duplicates, sort by highest score, and return top N matches.",
    run=aggregate_jobs
)