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


def test_from_env_normalizes_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_from_env_loads_every_supported_setting() -> None:
    """Every documented environment variable is parsed."""
    config = ScraperConfig.from_env(
        {
            "NETSKRAPE_USER_AGENT": "TestBot/2.0",
            "NETSKRAPE_REQUEST_TIMEOUT_SECONDS": "7.5",
            "NETSKRAPE_MAX_CONCURRENCY": "8",
            "NETSKRAPE_REQUESTS_PER_SECOND": "2.5",
            "NETSKRAPE_MAX_RETRIES": "4",
            "NETSKRAPE_RETRY_BACKOFF_SECONDS": "0.25",
            "NETSKRAPE_RESPECT_ROBOTS_TXT": "off",
            "NETSKRAPE_LOG_LEVEL": "warning",
        }
    )

    assert config == ScraperConfig(
        user_agent="TestBot/2.0",
        request_timeout_seconds=7.5,
        max_concurrency=8,
        requests_per_second=2.5,
        max_retries=4,
        retry_backoff_seconds=0.25,
        respect_robots_txt=False,
        log_level=LogLevel.WARNING,
    )


@pytest.mark.parametrize(
    "value",
    ["false", "0", "no", "off", "FALSE"],
)
def test_from_env_parses_false_boolean_values(value: str) -> None:
    """Supported false spellings are parsed consistently."""
    config = ScraperConfig.from_env(
        {"NETSKRAPE_RESPECT_ROBOTS_TXT": value}
    )

    assert not config.respect_robots_txt


def test_from_env_rejects_invalid_boolean() -> None:
    """Ambiguous boolean values are rejected."""
    with pytest.raises(ConfigurationError, match="must be one of"):
        ScraperConfig.from_env(
            {"NETSKRAPE_RESPECT_ROBOTS_TXT": "sometimes"}
        )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"user_agent": " "}, "user_agent"),
        ({"request_timeout_seconds": 0}, "request_timeout_seconds"),
        ({"max_concurrency": 0}, "max_concurrency"),
        ({"requests_per_second": 0}, "requests_per_second"),
        ({"max_retries": -1}, "max_retries"),
        ({"retry_backoff_seconds": -1}, "retry_backoff_seconds"),
        ({"requests_per_second": float("nan")}, "requests_per_second"),
        ({"request_timeout_seconds": float("inf")}, "request_timeout_seconds"),
    ],
)
def test_configuration_rejects_invalid_values(
    arguments: dict[str, str | int | float],
    message: str,
) -> None:
    """Direct construction receives the same validation guarantees."""
    with pytest.raises(ConfigurationError, match=message):
        ScraperConfig(**arguments)


def test_from_env_wraps_invalid_numeric_value() -> None:
    """Malformed numeric settings become configuration errors."""
    with pytest.raises(ConfigurationError, match="Invalid NetSkrape"):
        ScraperConfig.from_env(
            {"NETSKRAPE_MAX_CONCURRENCY": "many"}
        )
