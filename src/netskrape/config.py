"""Application configuration and environment loading."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from os import environ
from typing import Self

from netskrape.exceptions import ConfigurationError


DEFAULT_USER_AGENT = "NetSkrape/0.1"


class LogLevel(StrEnum):
    """Log levels supported by the application."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    """Validated configuration for the scraper application."""

    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 20.0
    max_concurrency: int = 5
    requests_per_second: float = 1.0
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    respect_robots_txt: bool = True
    log_level: LogLevel = LogLevel.INFO

    def __post_init__(self) -> None:
        """Validate configuration regardless of how it was constructed."""
        if not self.user_agent.strip():
            raise ConfigurationError("user_agent must not be empty")
        if (
            not isfinite(self.request_timeout_seconds)
            or self.request_timeout_seconds <= 0
        ):
            raise ConfigurationError(
                "request_timeout_seconds must be finite and greater than zero"
            )
        if self.max_concurrency <= 0:
            raise ConfigurationError(
                "max_concurrency must be greater than zero"
            )
        if (
            not isfinite(self.requests_per_second)
            or self.requests_per_second <= 0
        ):
            raise ConfigurationError(
                "requests_per_second must be finite and greater than zero"
            )
        if self.max_retries < 0:
            raise ConfigurationError("max_retries must not be negative")
        if (
            not isfinite(self.retry_backoff_seconds)
            or self.retry_backoff_seconds < 0
        ):
            raise ConfigurationError(
                "retry_backoff_seconds must be finite and not negative"
            )
        if not isinstance(self.respect_robots_txt, bool):
            raise ConfigurationError(
                "respect_robots_txt must be a boolean"
            )
        if not isinstance(self.log_level, LogLevel):
            raise ConfigurationError("log_level must be a LogLevel")

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] = environ,
    ) -> Self:
        """Construct validated configuration from an environment mapping."""
        try:
            return cls(
                user_agent=env.get(
                    "NETSKRAPE_USER_AGENT",
                    DEFAULT_USER_AGENT,
                ),
                request_timeout_seconds=float(
                    env.get(
                        "NETSKRAPE_REQUEST_TIMEOUT_SECONDS",
                        "20.0",
                    )
                ),
                max_concurrency=int(
                    env.get("NETSKRAPE_MAX_CONCURRENCY", "5")
                ),
                requests_per_second=float(
                    env.get("NETSKRAPE_REQUESTS_PER_SECOND", "1.0")
                ),
                max_retries=int(
                    env.get("NETSKRAPE_MAX_RETRIES", "3")
                ),
                retry_backoff_seconds=float(
                    env.get(
                        "NETSKRAPE_RETRY_BACKOFF_SECONDS",
                        "2.0",
                    )
                ),
                respect_robots_txt=_parse_bool(
                    env.get("NETSKRAPE_RESPECT_ROBOTS_TXT", "true"),
                    name="NETSKRAPE_RESPECT_ROBOTS_TXT",
                ),
                log_level=LogLevel(
                    env.get(
                        "NETSKRAPE_LOG_LEVEL",
                        LogLevel.INFO,
                    ).strip().upper()
                ),
            )
        except ConfigurationError:
            raise
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Invalid NetSkrape configuration: {error}"
            ) from error


def _parse_bool(value: str, *, name: str) -> bool:
    """Parse an explicit environment-style boolean value."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(
        f"{name} must be one of: true, false, 1, 0, yes, no, on, off"
    )
