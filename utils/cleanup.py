"""Removes previous runtime artifacts before a fresh run. Never touches
source code, POM, utilities, Excel test cases, or documentation."""
import shutil

from config.settings import SCREENSHOTS_DIR, LOGS_DIR, REPORTS_DIR


def clean_runtime():
    for bucket in ("PASS", "FAIL", "_pending"):
        d = SCREENSHOTS_DIR / bucket
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    if LOGS_DIR.exists():
        for item in LOGS_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    for name in ("automation_report.html", "execution_results.json", "live_state.json", "live_state.tmp"):
        f = REPORTS_DIR / name
        if f.exists():
            f.unlink()
