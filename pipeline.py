# =============================================
# orchestrator.py
# =============================================

from utils.pdf_reader import read_pdf
from agents.resume_parser import parse_resume
from agents.matcher import match_jobs
from agents.ranking import rank_jobs
from agents.aggregator import aggregate_jobs
from apis.remotive import fetch_remotive_jobs
from apis.arbeitnow import fetch_arbeitnow_jobs


def run_pipeline():
    """Main system workflow."""

    # 1. Load resume
    text = read_pdf("data/resume.pdf")

    # 2. Parse profile
    profile = parse_resume(text)

    # 3. Fetch jobs (parallel conceptually)
    remotive_jobs = fetch_remotive_jobs()
    arbeitnow_jobs = fetch_arbeitnow_jobs()

    # 4. Match
    matched_1 = match_jobs(profile, remotive_jobs)
    matched_2 = match_jobs(profile, arbeitnow_jobs)

    # 5. Combine
    all_jobs = matched_1 + matched_2

    # 6. Rank
    ranked_jobs = rank_jobs(profile, all_jobs)

    # 7. Aggregate (IMPORTANT STEP)
    final_jobs = aggregate_jobs(ranked_jobs)

    return final_jobs

