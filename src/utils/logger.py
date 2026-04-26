from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    from src.config.settings import settings

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "[%(levelname)s] %(name)s — %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
        logger.propagate = False
    return logger
