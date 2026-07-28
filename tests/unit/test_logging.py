"""Unit tests for application logging helpers."""

import logging
from io import StringIO

from netskrape.config import LogLevel
from netskrape.logging import configure_logging, safe_url


def test_configure_logging_applies_level_and_format() -> None:
    """Configured application messages include level, logger, and text."""
    stream = StringIO()
    configure_logging(LogLevel.WARNING, stream=stream)

    logger = logging.getLogger("netskrape.test")
    logger.info("hidden")
    logger.warning("visible")

    output = stream.getvalue()
    assert "hidden" not in output
    assert "WARNING netskrape.test: visible" in output


def test_safe_url_redacts_sensitive_components() -> None:
    """Credentials, queries, and fragments are excluded from logged URLs."""
    sanitized = safe_url(
        "https://user:secret@example.com:8443/path"
        "?token=secret#section"
    )

    assert sanitized == "https://example.com:8443/path?<redacted>"
    assert "secret" not in sanitized
    assert "user" not in sanitized
    assert "section" not in sanitized


def test_safe_url_handles_invalid_port() -> None:
    """Malformed URLs produce a safe placeholder."""
    assert safe_url("https://example.com:invalid") == "<invalid-url>"
