# =============================================
# agents/aggregator.py
# =============================================


def aggregate_jobs(ranked_jobs: list, top_n: int = 10) -> list:
    """
    Clean + finalize results.

    Responsibilities:
    - Deduplicate
    - Keep best score
    - Sort
    - Limit output
    """

    unique = {}

    for item in ranked_jobs:
        job = item["job"]
        score = item["score"]

        key = f"{job.get('title')}_{job.get('company')}"

        if key not in unique or unique[key]["score"] < score:
            unique[key] = item

    result = list(unique.values())
    result.sort(key=lambda x: x["score"], reverse=True)

    return result[:top_n]
