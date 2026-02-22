"""Logging configuration for SAN Zone Designer web interface."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "database" / "logs"
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger: console + rotating file handler."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler — keeps last 5 × 5 MB files
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "san_zone_designer.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
