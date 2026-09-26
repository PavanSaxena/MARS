import logging
import os
import sys
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """Configure structured logging across the application."""
    level_name = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress overly verbose third-party loggers
    for noisy in ("httpcore", "httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root_logger = logging.getLogger("mars")
    root_logger.setLevel(level)
    root_logger.info(f"Logging initialized at level: {level_name}")
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger prefixed under the 'mars' namespace."""
    return logging.getLogger(f"mars.{name}")
