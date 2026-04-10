# =============================================
# apis/arbeitnow.py
# =============================================
import requests
from agents import Agent, Runner, function_tool

@function_tool
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
