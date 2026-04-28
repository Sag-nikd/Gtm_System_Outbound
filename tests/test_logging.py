"""Tests for structured logging — text and JSON format options."""
from __future__ import annotations

import io
import json
import logging

import pytest


def _captured_logger(name: str, log_format: str):
    """Return (logger, StringIO) with the correct formatter for log_format."""
    import src.utils.logger as logger_mod

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    if log_format == "json":
        handler.setFormatter(logger_mod._JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s — %(message)s")
        )

    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger, stream


def test_text_format_produces_bracketed_output():
    logger, stream = _captured_logger("test.text", "text")
    logger.warning("hello world")
    output = stream.getvalue()
    assert "hello world" in output
    assert "[WARNING]" in output


def test_json_format_produces_valid_json():
    logger, stream = _captured_logger("test.json", "json")
    logger.warning("test json message")
    output = stream.getvalue().strip()
    assert output, "Expected log output"

    parsed = json.loads(output)
    assert "message" in parsed
    assert "level" in parsed
    assert "timestamp" in parsed
    assert "logger" in parsed


def test_json_format_message_field_matches():
    logger, stream = _captured_logger("test.json.msg", "json")
    logger.info("unique-message-xyz-123")
    output = stream.getvalue().strip()
    parsed = json.loads(output)
    assert parsed["message"] == "unique-message-xyz-123"
    assert parsed["level"] == "INFO"


def test_json_formatter_is_importable():
    from src.utils.logger import _JsonFormatter
    assert _JsonFormatter is not None


def test_create_logger_is_importable():
    from src.utils.logger import _create_logger
    assert _create_logger is not None
