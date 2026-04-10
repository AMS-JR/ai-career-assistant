# =============================================
# Application entry (repo root)
# =============================================

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(levelname)s %(name)s: %(message)s",
)

from ui.app import run_app


def main() -> None:
    run_app()


if __name__ == "__main__":
    main()
