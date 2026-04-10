# =============================================
# apis/remotive.py
# =============================================
import requests
from agents import Agent, Runner, function_tool

@function_tool
def fetch_remotive_jobs(search: str = "", category: str = "", limit: int = 100):
    url = "https://remotive.com/api/remote-jobs"
    params = {
        "search": search,
        "category": category,
        "limit": limit,
    }
    params = {k: v for k, v in params.items() if v not in (None, "")}
    data = requests.get(url, params=params, timeout=30).json()

    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company_name"),
            "category": job.get("category"),
            "location": job.get("candidate_required_location") or "Fully Remote",
            "description": job.get("description"),
            "url": job.get("url")
        })
    return jobs

