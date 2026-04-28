"""Tests for the api_retry decorator — 429 handling and exponential backoff."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call

import pytest
import requests


def _make_http_error(status_code: int, headers: dict = None) -> requests.HTTPError:
    """Create a requests.HTTPError with a mock response."""
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    err = requests.HTTPError(response=response)
    return err


def test_429_with_retry_after_header_retries_and_succeeds():
    """Function raising 429 with Retry-After: 1 is retried and succeeds on second call."""
    from src.utils.retry import api_retry

    call_count = [0]

    @api_retry
    def flaky():
        call_count[0] += 1
        if call_count[0] == 1:
            raise _make_http_error(429, {"Retry-After": "1"})
        return "ok"

    with patch("time.sleep"):  # suppress actual sleeping in tests
        result = flaky()

    assert result == "ok"
    assert call_count[0] == 2


def test_500_uses_exponential_backoff():
    """Function raising 500 (non-429) is retried with exponential backoff."""
    from src.utils.retry import api_retry

    call_count = [0]

    @api_retry
    def always_500():
        call_count[0] += 1
        raise _make_http_error(500)

    with patch("time.sleep"):
        with pytest.raises(requests.HTTPError):
            always_500()

    assert call_count[0] >= 2  # retried at least once before giving up


def test_429_three_times_then_succeeds():
    """Function raising 429 three times then succeeds on fourth call."""
    from src.utils.retry import api_retry

    call_count = [0]

    @api_retry
    def three_429s():
        call_count[0] += 1
        if call_count[0] < 4:
            raise _make_http_error(429, {"Retry-After": "1"})
        return "success"

    with patch("time.sleep"):
        result = three_429s()

    assert result == "success"
    assert call_count[0] == 4


def test_non_http_error_retries():
    """ConnectionError is retried via the existing mechanism."""
    from src.utils.retry import api_retry

    call_count = [0]

    @api_retry
    def network_blip():
        call_count[0] += 1
        if call_count[0] < 2:
            raise ConnectionError("temporary network failure")
        return "connected"

    with patch("time.sleep"):
        result = network_blip()

    assert result == "connected"
    assert call_count[0] == 2
