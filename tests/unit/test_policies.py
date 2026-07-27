"""Unit tests for crawl policies."""

from urllib.robotparser import RobotFileParser

import pytest

from netskrape.crawling.policies import (
    CrawlPolicy,
    RateLimitPolicy,
    RetryPolicy,
    RobotsPolicy,
)


def test_retry_policy_retries_transient_status_within_limit() -> None:
    policy = RetryPolicy(max_retries=2)

    assert policy.should_retry(503, attempt=0)
    assert policy.should_retry(503, attempt=1)
    assert not policy.should_retry(503, attempt=2)
    assert not policy.should_retry(404, attempt=0)


def test_retry_policy_calculates_capped_deterministic_backoff() -> None:
    policy = RetryPolicy(
        backoff_seconds=2,
        max_backoff_seconds=5,
        jitter_ratio=0.25,
    )

    assert policy.delay_for(0, jitter=0) == 2
    assert policy.delay_for(1, jitter=1) == 5
    assert policy.delay_for(3, jitter=0) == 5


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"max_retries": -1}, "max_retries"),
        ({"backoff_seconds": -1}, "backoff_seconds"),
        ({"jitter_ratio": 1.1}, "jitter_ratio"),
    ],
)
def test_retry_policy_rejects_invalid_configuration(
    arguments: dict[str, int | float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**arguments)


def test_rate_limit_policy_reports_remaining_delay() -> None:
    policy = RateLimitPolicy(requests_per_second=2)

    assert policy.delay_seconds == 0.5
    assert policy.delay_remaining(None, current_time=10) == 0
    assert policy.delay_remaining(10, current_time=10.2) == pytest.approx(0.3)
    assert policy.allows_request(10, current_time=10.5)


def test_rate_limit_policy_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        RateLimitPolicy(requests_per_second=0)


def test_robots_policy_applies_parsed_rules() -> None:
    rules = RobotFileParser()
    rules.parse(["User-agent: NetSkrape", "Disallow: /private"])
    policy = RobotsPolicy(user_agent="NetSkrape")

    assert policy.allows("https://example.com/public", rules)
    assert not policy.allows("https://example.com/private", rules)


def test_robots_policy_fails_closed_when_rules_are_unavailable() -> None:
    policy = RobotsPolicy(user_agent="NetSkrape")

    assert not policy.allows("https://example.com", rules=None)


def test_crawl_policy_restricts_scheme_domain_and_depth() -> None:
    policy = CrawlPolicy(
        allowed_domains=frozenset({"example.com"}),
        max_depth=2,
    )

    assert policy.allows("https://example.com/start", depth=0)
    assert policy.allows("https://docs.example.com/page", depth=2)
    assert not policy.allows("ftp://example.com/file", depth=1)
    assert not policy.allows("https://example.net/page", depth=1)
    assert not policy.allows("https://example.com/deep", depth=3)


def test_crawl_policy_does_not_confuse_domain_suffixes() -> None:
    policy = CrawlPolicy(allowed_domains=frozenset({"example.com"}))

    assert not policy.allows("https://notexample.com", depth=0)
