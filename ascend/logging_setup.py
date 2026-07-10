"""Rotating local logging for Ascend.

Never log secrets: client secret, OAuth access tokens, Discord webhook URL,
GitHub credentials, or Windows Credential Manager contents. Only log
non-sensitive operational events (startup, sync status, API/GraphQL errors,
rate limits, analysis/export/background-worker failures).
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOGGER_NAME = "ascend"

_configured = False


def setup_logging(log_dir: Path, level: int = logging.INFO, force: bool = False) -> logging.Logger:
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "ascend.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
