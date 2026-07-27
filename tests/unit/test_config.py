"""Unit tests for application configuration."""

import pytest

from netskrape.config import DEFAULT_USER_AGENT, LogLevel, ScraperConfig
from netskrape.exceptions import ConfigurationError


def test_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing environment variables produce the documented defaults."""
    monkeypatch.delenv("NETSKRAPE_USER_AGENT", raising=False)
    monkeypatch.delenv("NETSKRAPE_LOG_LEVEL", raising=False)

    config = ScraperConfig.from_env()

    assert config.user_agent == DEFAULT_USER_AGENT
    assert config.log_level is LogLevel.INFO


def test_from_env_normalizes_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Log levels are accepted without requiring uppercase input."""
    monkeypatch.setenv("NETSKRAPE_LOG_LEVEL", "debug")

    assert ScraperConfig.from_env().log_level is LogLevel.DEBUG


def test_from_env_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid log levels raise the package configuration exception."""
    monkeypatch.setenv("NETSKRAPE_LOG_LEVEL", "verbose")

    with pytest.raises(ConfigurationError, match="Invalid NetSkrape"):
        ScraperConfig.from_env()
