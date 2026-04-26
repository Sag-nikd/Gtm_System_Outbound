from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def api_retry(func):
    """
    Decorator for retrying real API client methods with exponential backoff.
    Retries up to 3 times on network or connection errors.
    Not applied to mock clients.
    """
    import requests

    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )(func)
