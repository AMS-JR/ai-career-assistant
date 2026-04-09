# =============================================
# orchestrator.py
# =============================================

from utils.pdf_reader import read_pdf
from career_agents.resume_parser import parse_resume
# from career_agents.matcher import match_jobs
# from career_agents.ranking import rank_jobs
# from career_agents.aggregator import aggregate_jobs
# from career_agents.RankingAgent import RankingAgent
# from career_agents.remotive_matcher import match_remotive_jobs
# from career_agents.arbeitnow_matcher import match_arbeitnow_jobs


import asyncio
from agents import Runner

def run_pipeline():
    """Main system workflow."""

    # 1. Load resume
    text = read_pdf("data/resume.pdf")

    # 2. Parse profile
    profile = parse_resume(text)
    print(profile)

    # # 3. Async job matching
    async def run_parallel_agents():
        remotive_task = Runner.run(match_remotive_jobs, text)
        arbeitnow_task = Runner.run(match_arbeitnow_jobs, text)

        remotive_result, arbeitnow_result = await asyncio.gather(
            remotive_task,
            arbeitnow_task
        )
        # 4. Combine matches
        all_jobs = remotive_result.final_output + arbeitnow_result.final_output
        return all_jobs

    # 🔥 Run async function properly
    all_jobs = asyncio.run(run_parallel_agents())

    # # # 4. Combine matches
    # # all_jobs = remotive_jobs + arbeitnow_jobs

    # # 5. Rank
    # ranked_result = RankingAgent.run(profile, all_jobs)

    # # 6. Aggregate top matches
    # final_jobs = AggregatorAgent.run(ranked_jobs, top_n=50)

    # return final_jobs
    return "Help"