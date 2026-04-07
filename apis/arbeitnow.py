# =============================================
# apis/arbeitnow.py
# =============================================
import requests


def fetch_arbeitnow_jobs():
    url = "https://www.arbeitnow.com/api/job-board-api"
    data = requests.get(url).json()

    jobs = []
    for job in data.get("data", []):
        jobs.append({
            "title": job.get("title"),
            "company": job.get("company_name"),
            "description": job.get("description"),
            "url": job.get("url")
        })
    return jobs
