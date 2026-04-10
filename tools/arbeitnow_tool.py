# apis/arbeitnow.py
# =============================================

import httpx
from agents import function_tool


@function_tool
def fetch_arbeitnow_jobs(search: str) -> list:
    """
    Fetch job listings from Arbeitnow's public API.

    Args:
        search: keyword to search for (e.g. "python backend", "data engineer")

    Returns:
        A list of job dictionaries with keys:
        slug, title, company_name, location, remote,
        tags, job_types, description, url, created_at
    """

    url = "https://www.arbeitnow.com/api/job-board-api"
    params = {"search": search}

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Jobs are nested under "data" key
        return data.get("data", [])

    except httpx.HTTPError as e:
        print(f"[fetch_arbeitnow_jobs] HTTP error: {e}")
        return []
    except Exception as e:
        print(f"[fetch_arbeitnow_jobs] Unexpected error: {e}")
        return []
