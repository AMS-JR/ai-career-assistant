# Thin shim so `python main.py` from repo root runs the packaged app.
from career_assistant.main import main

if __name__ == "__main__":
    main()
