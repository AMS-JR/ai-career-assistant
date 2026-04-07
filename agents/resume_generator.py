# =============================================
# agents/resume_generator.py
# =============================================


def generate_tailored_resume(profile: dict, job: dict):
    """
    Generates a simple tailored resume file.
    """

    filename = f"{profile.get('name', 'User').replace(' ', '')}_Resume.txt"

    with open(filename, "w") as f:
        f.write("TAILORED RESUME\n\n")
        f.write(str(profile))
        f.write("\n\nJOB TARGET:\n")
        f.write(str(job))

    return filename
