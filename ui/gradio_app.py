# =============================================
# ui/gradio_app.py
# =============================================

import gradio as gr
from pipeline import run_pipeline


def run_app():

    def get_jobs():
        jobs = run_pipeline()

        output = ""
        for item in jobs:
            job = item["job"]
            output += f"""
Title: {job.get('title')}
Company: {job.get('company')}
Score: {item['score']}
Apply: {job.get('url')}
--------------------------
"""
        return output

    demo = gr.Interface(
        fn=get_jobs,
        inputs=[],
        outputs="text",
        title="AI Career Assistant"
    )

    demo.launch()

