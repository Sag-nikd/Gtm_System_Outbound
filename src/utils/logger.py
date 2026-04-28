from __future__ import annotations

import json
import logging


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


def _create_logger(name: str, log_format: str) -> logging.Logger:
    """Create (or reconfigure) a logger with either text or JSON formatting."""
    logger = logging.getLogger(name)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s — %(message)s")
        )

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    from src.config.settings import settings

    logger = logging.getLogger(name)
    if not logger.handlers:
        _create_logger(name, settings.LOG_FORMAT)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    return logger
