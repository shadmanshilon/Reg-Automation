"""Feature-scoped logger: writes to logs/<Feature>/<Feature>.log and echoes
to the terminal so headed runs show live progress."""
import logging
import sys
from pathlib import Path

from config.settings import LOGS_DIR


def get_logger(feature: str) -> logging.Logger:
    feature_dir = LOGS_DIR / feature
    feature_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"qa.{feature}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(feature_dir / f"{feature}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


def step(logger: logging.Logger, n: int, text: str):
    logger.info("STEP %d - %s", n, text)


def action(logger: logging.Logger, text: str):
    logger.info("ACTION - %s", text)


def assertion(logger: logging.Logger, text: str, passed: bool, expected=None, actual=None):
    mark = "PASS" if passed else "FAIL"
    logger.info("[ASSERTION] %-55s %s", text, mark)
    if not passed:
        logger.info("    Expected: %s", expected)
        logger.info("    Actual:   %s", actual)
