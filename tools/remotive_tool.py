# apis/remotive.py
# =============================================

import httpx
from agents import function_tool


@function_tool
def fetch_remotive_jobs(search: str, category: str, limit: int = 100) -> list:
    """
    Fetch remote job listings from Remotive's public API.

    Args:
        search:   keyword to search for (e.g. "python", "data engineer")
        category: job category (e.g. "software-dev", "data", "devops")
        limit:    number of results to return (default 100)

    Returns:
        A list of job dictionaries with keys:
        id, title, company, candidate_required_location,
        description, url, tags, job_type, salary, created_at
    """

    url = "https://remotive.com/api/remote-jobs"
    params = {
        "search": search,
        "category": category,
        "limit": limit,
    }

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Jobs are at root level under "jobs" key
        return data.get("jobs", [])

    except httpx.HTTPError as e:
        print(f"[fetch_remotive_jobs] HTTP error: {e}")
        return []
    except Exception as e:
        print(f"[fetch_remotive_jobs] Unexpected error: {e}")
        return []
