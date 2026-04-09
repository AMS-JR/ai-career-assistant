# =============================================
# apis/remotive.py
# =============================================
import requests
from agents import Agent, Runner, function_tool

@function_tool
def fetch_remotive_jobs():
    url = "https://remotive.com/api/remote-jobs"
    data = requests.get(url).json()

    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "title": job.get("title"),
            "company": job.get("company_name"),
            "description": job.get("description"),
            "url": job.get("url")
        })
    return jobs

