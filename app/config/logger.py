"""
Centralized logging configuration.

Log files are written to logs/log_<date>.log at project root.
"""

import logging
from datetime import datetime
from pathlib import Path

# Project root directory (guardrail_poc)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def setup_logging(level: int = logging.INFO, log_dir: str | Path | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Creates the log directory at project root if it doesn't exist, and sets up
    a file handler with date-stamped log files plus a console handler.
    """
    if log_dir is None:
        log_dir = PROJECT_ROOT / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"log_{date_str}.log"

    logger = logging.getLogger("guardrail_poc")

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s.%(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — daily log file
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a child logger under the guardrail_poc namespace.

    Usage:
        from app.config.logger import get_logger
        log = get_logger(__name__)
        log.info("something happened")
    """
    base = logging.getLogger("guardrail_poc")
    if not base.handlers:
        setup_logging()
    if name:
        return base.getChild(name)
    return base
