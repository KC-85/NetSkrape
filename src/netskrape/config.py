"""Application configuration and environment loading."""

from dataclasses import dataclass
from enum import StrEnum
from os import environ
from typing import Self

from netskrape.exceptions import ConfigurationError


DEFAULT_USER_AGENT = "NetSkrape/0.1"


class LogLevel(StrEnum):
    """Log levels for the application."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    """Configuration for the scraper application."""

    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 20.0
    max_concurrency: int = 5
    requests_per_second: float = 1.0
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    respect_robots_txt: bool = True
    log_level: LogLevel = LogLevel.INFO

    @classmethod
    def from_env(cls) -> Self:
        """Construct configuration from environment variables."""
        try:
            return cls(
                user_agent=environ.get(
                    "NETSKRAPE_USER_AGENT",
                    DEFAULT_USER_AGENT,
                ),
                log_level=LogLevel(
                    environ.get(
                        "NETSKRAPE_LOG_LEVEL",
                        LogLevel.INFO,
                    ).upper()
                ),
            )
        except ValueError as error:
            raise ConfigurationError(
                f"Invalid NetSkrape configuration: {error}"
            ) from error
