"""Unit tests for the asynchronous scraper client."""

import httpx
import pytest

from netskrape.config import ScraperConfig
from netskrape.crawling.client import ScraperClient
from netskrape.crawling.policies import (
    CrawlPolicy,
    RateLimitPolicy,
    RetryPolicy,
    RobotsPolicy,
)
from netskrape.exceptions import FetchError


def make_client(
    handler: httpx.AsyncBaseTransport,
    *,
    crawl_policy: CrawlPolicy | None = None,
    retry_policy: RetryPolicy | None = None,
    respect_robots_txt: bool = False,
) -> ScraperClient:
    """Create a fast client backed by an in-memory HTTP transport."""
    config = ScraperConfig(
        max_retries=1,
        retry_backoff_seconds=0,
        respect_robots_txt=respect_robots_txt,
    )
    return ScraperClient(
        config,
        crawl_policy=crawl_policy,
        retry_policy=retry_policy,
        rate_limit_policy=RateLimitPolicy(requests_per_second=1_000_000),
        robots_policy=RobotsPolicy(
            user_agent=config.user_agent,
            respect_robots_txt=respect_robots_txt,
        ),
        transport=handler,
    )


@pytest.mark.asyncio
async def test_fetch_returns_successful_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "NetSkrape/0.1"
        return httpx.Response(200, text="content")

    async with make_client(httpx.MockTransport(handler)) as client:
        response = await client.fetch("https://example.com/page")

    assert response.text == "content"


@pytest.mark.asyncio
async def test_fetch_retries_transient_response() -> None:
    status_codes = iter([503, 200])

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(status_codes))

    retry_policy = RetryPolicy(
        max_retries=1,
        backoff_seconds=0,
        jitter_ratio=0,
    )
    async with make_client(
        httpx.MockTransport(handler),
        retry_policy=retry_policy,
    ) as client:
        response = await client.fetch("https://example.com/page")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_fetch_translates_final_http_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404)
    )

    async with make_client(transport) as client:
        with pytest.raises(FetchError, match="HTTP 404"):
            await client.fetch("https://example.com/missing")


@pytest.mark.asyncio
async def test_fetch_rejects_url_outside_crawl_scope() -> None:
    policy = CrawlPolicy(allowed_domains=frozenset({"example.com"}))
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200)
    )

    async with make_client(
        transport,
        crawl_policy=policy,
    ) as client:
        with pytest.raises(FetchError, match="outside"):
            await client.fetch("https://example.net/page")


@pytest.mark.asyncio
async def test_fetch_rejects_redirect_outside_crawl_scope() -> None:
    policy = CrawlPolicy(allowed_domains=frozenset({"example.com"}))
    requested_hosts: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(
            302,
            headers={"Location": "https://example.net/page"},
        )

    async with make_client(
        httpx.MockTransport(handler),
        crawl_policy=policy,
    ) as client:
        with pytest.raises(FetchError, match="outside"):
            await client.fetch("https://example.com/start")

    assert requested_hosts == ["example.com"]


@pytest.mark.asyncio
async def test_fetch_applies_and_caches_robots_rules() -> None:
    requested_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: NetSkrape\nDisallow: /private",
            )
        return httpx.Response(200)

    async with make_client(
        httpx.MockTransport(handler),
        respect_robots_txt=True,
    ) as client:
        await client.fetch("https://example.com/public")
        with pytest.raises(FetchError, match="robots.txt"):
            await client.fetch("https://example.com/private")

    assert requested_paths.count("/robots.txt") == 1
