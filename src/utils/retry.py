from __future__ import annotations

import time

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryCallState,
)


def _is_429(exc: BaseException) -> bool:
    import requests
    return (
        isinstance(exc, requests.HTTPError)
        and getattr(getattr(exc, "response", None), "status_code", None) == 429
    )


def _before_sleep_handle_429(retry_state: RetryCallState) -> None:
    """If the last exception was a 429, honour the Retry-After header before sleeping."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc is not None and _is_429(exc):
        retry_after = getattr(exc.response, "headers", {}).get("Retry-After")
        if retry_after is not None:
            try:
                time.sleep(float(retry_after))
                return
            except (ValueError, TypeError):
                pass
    # For non-429 errors, tenacity's wait_exponential handles the delay


def api_retry(func):
    """
    Decorator for retrying real API client methods.
    - HTTP 429: retries up to 5 times, honouring the Retry-After header when present.
    - Other network/connection errors: exponential backoff, up to 5 attempts.
    Not applied to mock clients.
    """
    import requests

    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.HTTPError, requests.RequestException, ConnectionError)
        ),
        before_sleep=_before_sleep_handle_429,
        reraise=True,
    )(func)
