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
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    level_name = os.getenv("TRAVEL_PLANNER_LOG_LEVEL")
    if level_name:
        logging.disable(logging.NOTSET)
        logging.basicConfig(level=_resolve_level(level_name), format=DEFAULT_FORMAT)
    else:
        logging.basicConfig(level=logging.CRITICAL, format=DEFAULT_FORMAT)
        logging.disable(logging.CRITICAL)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)
