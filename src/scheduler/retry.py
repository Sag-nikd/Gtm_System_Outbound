"""
Retry logic for individual stage executions.
Reads per-stage config from config/scheduler.json.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

_RETRYABLE_ERRORS = ("ConnectionError", "HTTPError", "Timeout", "RequestException")
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_DELAY = 60


def get_retry_config(stage_name: str, scheduler_cfg: dict) -> dict:
    stage_cfg = scheduler_cfg.get(stage_name, {})
    return {
        "max_retries": stage_cfg.get("max_retries", scheduler_cfg.get("defaults", {}).get("max_retries", _DEFAULT_MAX_RETRIES)),
        "retry_delay_seconds": stage_cfg.get("retry_delay_seconds", scheduler_cfg.get("defaults", {}).get("retry_delay_seconds", _DEFAULT_DELAY)),
        "retry_on": stage_cfg.get("retry_on", list(_RETRYABLE_ERRORS)),
    }


def is_retryable_error(exc: Exception, retry_on: list) -> bool:
    exc_type = type(exc).__name__
    # Also check MRO for base classes.
    for cls in type(exc).__mro__:
        if cls.__name__ in retry_on:
            return True
    return exc_type in retry_on


def run_with_retry(
    stage_fn: Callable,
    run_context: dict,
    stage_name: str,
    scheduler_cfg: dict,
    on_attempt: Optional[Callable[[int, Exception], None]] = None,
) -> Any:
    """
    Call stage_fn(run_context) with exponential-backoff retry on transient errors.
    Non-retryable errors propagate immediately.
    """
    from src.utils.logger import get_logger
    log = get_logger(__name__)

    cfg = get_retry_config(stage_name, scheduler_cfg)
    max_retries = cfg["max_retries"]
    delay = cfg["retry_delay_seconds"]
    retry_on = cfg["retry_on"]

    attempt = 1
    while True:
        try:
            return stage_fn(run_context)
        except Exception as exc:
            if not is_retryable_error(exc, retry_on):
                log.error(
                    "%s failed with non-retryable error (%s): %s",
                    stage_name, type(exc).__name__, exc,
                )
                raise
            if attempt > max_retries:
                log.error(
                    "%s failed after %d attempts: %s", stage_name, attempt, exc
                )
                raise
            wait = delay * (2 ** (attempt - 1))
            log.warning(
                "%s attempt %d/%d failed (%s: %s) — retrying in %ds",
                stage_name, attempt, max_retries + 1, type(exc).__name__, exc, wait,
            )
            if on_attempt:
                on_attempt(attempt, exc)
            time.sleep(wait)
            attempt += 1
