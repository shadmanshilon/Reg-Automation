"""Central configuration, read from .env. Changing .env changes the next run
without touching this file."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = os.getenv("BASE_URL", "").strip()
LOGIN_EMAIL = os.getenv("LOGIN_EMAIL", "").strip()
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "").strip()
HEADLESS = os.getenv("HEADLESS", "false").strip().lower() == "true"
BROWSER = os.getenv("BROWSER", "chromium").strip()
TIMEOUT = int(os.getenv("TIMEOUT", "30000"))
DEPLOYMENT_SUCCESS_THRESHOLD = float(os.getenv("DEPLOYMENT_SUCCESS_THRESHOLD", "95"))

SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEST_DATA_DIR = PROJECT_ROOT / "test_data"

if not BASE_URL or not LOGIN_EMAIL or not LOGIN_PASSWORD:
    raise RuntimeError(
        "BASE_URL / LOGIN_EMAIL / LOGIN_PASSWORD must be set in .env "
        "(see .env.example)."
    )
