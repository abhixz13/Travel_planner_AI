"""Application-wide logging helpers."""

from __future__ import annotations
import logging
import os
from typing import Optional

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "openai",
    "langchain",
    "langgraph",
)


def _resolve_level(level_name: Optional[str]) -> int:
    """Translate an env-provided level string into a logging level."""
    if not level_name:
        return logging.INFO
    level = getattr(logging, level_name.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO


def configure_logging() -> None:
    """Configure root logging only once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level_name = os.getenv("TRAVEL_PLANNER_LOG_LEVEL", "INFO")
    logging.basicConfig(level=_resolve_level(level_name), format=DEFAULT_FORMAT)

    # Quiet noisy third-party loggers unless explicitly raised via env vars.
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
