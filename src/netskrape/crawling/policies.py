"""Retry, rate-limit, robots, and crawl policy definitions."""

from dataclasses import dataclass, field
from random import uniform
from typing import Protocol
from urllib.parse import urlparse


DEFAULT_RETRYABLE_STATUS_CODES = frozenset(
    {408, 425, 429, 500, 502, 503, 504}
)


class RobotsRules(Protocol):
    """Interface implemented by parsed robots.txt rule sets."""

    def can_fetch(self, user_agent: str, url: str) -> bool:
        """Return whether a user agent may fetch a URL."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Decide whether and when a failed request should be retried.

    ``attempt`` is zero-based: zero represents the first retry after the
    initial request fails.
    """

    max_retries: int = 3
    backoff_seconds: float = 2.0
    max_backoff_seconds: float = 60.0
    jitter_ratio: float = 0.25
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_STATUS_CODES
    )

    def __post_init__(self) -> None:
        """Validate retry settings."""
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")
        if self.max_backoff_seconds < 0:
            raise ValueError("max_backoff_seconds must not be negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")
        if any(not 100 <= code <= 599 for code in self.retryable_status_codes):
            raise ValueError(
                "retryable status codes must be valid HTTP statuses"
            )

    def should_retry(self, status_code: int, attempt: int) -> bool:
        """Return whether an HTTP response should be retried."""
        if attempt < 0:
            raise ValueError("attempt must not be negative")
        return (
            attempt < self.max_retries
            and status_code in self.retryable_status_codes
        )

    def delay_for(self, attempt: int, *, jitter: float | None = None) -> float:
        """Return capped exponential backoff with proportional jitter.

        Supplying ``jitter`` makes tests and callers deterministic. Its value
        must be between zero and one.
        """
        if attempt < 0:
            raise ValueError("attempt must not be negative")
        if jitter is None:
            jitter = uniform(0.0, 1.0)
        if not 0 <= jitter <= 1:
            raise ValueError("jitter must be between 0 and 1")

        base_delay = min(
            self.backoff_seconds * (2**attempt),
            self.max_backoff_seconds,
        )
        return base_delay * (1 + self.jitter_ratio * jitter)


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Control the minimum interval between requests to one origin."""

    requests_per_second: float = 1.0

    def __post_init__(self) -> None:
        """Validate rate-limit settings."""
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than zero")

    @property
    def delay_seconds(self) -> float:
        """Return the minimum interval between consecutive requests."""
        return 1.0 / self.requests_per_second

    def delay_remaining(
        self,
        last_request_time: float | None,
        current_time: float,
    ) -> float:
        """Return how many seconds remain before another request is allowed."""
        if last_request_time is None:
            return 0.0
        return max(
            0.0,
            self.delay_seconds - (current_time - last_request_time),
        )

    def allows_request(
        self,
        last_request_time: float | None,
        current_time: float,
    ) -> bool:
        """Return whether enough time has elapsed for another request."""
        return self.delay_remaining(last_request_time, current_time) == 0.0


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    """Decide whether robots.txt rules permit a request."""

    user_agent: str
    respect_robots_txt: bool = True
    allow_when_unavailable: bool = False

    def __post_init__(self) -> None:
        """Validate robots policy settings."""
        if not self.user_agent.strip():
            raise ValueError("user_agent must not be empty")

    def allows(self, url: str, rules: RobotsRules | None) -> bool:
        """Return whether a URL may be fetched under the supplied rules."""
        if not self.respect_robots_txt:
            return True
        if rules is None:
            return self.allow_when_unavailable
        return rules.can_fetch(self.user_agent, url)


@dataclass(frozen=True, slots=True)
class CrawlPolicy:
    """Restrict URLs and traversal depth for a crawl."""

    allowed_domains: frozenset[str] = field(default_factory=frozenset)
    allowed_schemes: frozenset[str] = field(
        default_factory=lambda: frozenset({"http", "https"})
    )
    max_depth: int = 3
    allow_subdomains: bool = True

    def __post_init__(self) -> None:
        """Validate and normalize crawl scope."""
        if self.max_depth < 0:
            raise ValueError("max_depth must not be negative")
        if not self.allowed_schemes:
            raise ValueError("allowed_schemes must not be empty")
        if any(not domain.strip() for domain in self.allowed_domains):
            raise ValueError("allowed_domains must not contain empty values")

        object.__setattr__(
            self,
            "allowed_domains",
            frozenset(
                domain.lower().rstrip(".")
                for domain in self.allowed_domains
            ),
        )
        object.__setattr__(
            self,
            "allowed_schemes",
            frozenset(scheme.lower() for scheme in self.allowed_schemes),
        )

    def allows(self, url: str, *, depth: int) -> bool:
        """Return whether a URL is within the configured crawl scope."""
        if depth < 0:
            raise ValueError("depth must not be negative")
        if depth > self.max_depth:
            return False

        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if (
            parsed_url.scheme.lower() not in self.allowed_schemes
            or hostname is None
        ):
            return False
        if not self.allowed_domains:
            return True

        normalized_host = hostname.lower().rstrip(".")
        return any(
            normalized_host == domain
            or (
                self.allow_subdomains
                and normalized_host.endswith(f".{domain}")
            )
            for domain in self.allowed_domains
        )
