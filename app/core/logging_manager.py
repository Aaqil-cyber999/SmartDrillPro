"""Central logging setup.

Errors are written to a rotating log file so a user can send us useful
diagnostics without seeing raw Python tracebacks in the interface.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("smartdrill")
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        file_handler = RotatingFileHandler(
            log_dir / "smartdrill.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(file_handler)

        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console)

    return logger
