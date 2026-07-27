"""Asynchronous HTTP transport for scraper requests."""

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic
from types import TracebackType
from typing import Self
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from netskrape.config import ScraperConfig
from netskrape.crawling.policies import (
    CrawlPolicy,
    RateLimitPolicy,
    RetryPolicy,
    RobotsPolicy,
)
from netskrape.exceptions import FetchError


MAX_REDIRECTS = 10


class ScraperClient:
    """Fetch web resources while applying crawl and politeness policies."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        crawl_policy: CrawlPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        robots_policy: RobotsPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create a client from application configuration and policies."""
        self._crawl_policy = crawl_policy or CrawlPolicy()
        self._retry_policy = retry_policy or RetryPolicy(
            max_retries=config.max_retries,
            backoff_seconds=config.retry_backoff_seconds,
        )
        self._rate_limit_policy = rate_limit_policy or RateLimitPolicy(
            requests_per_second=config.requests_per_second
        )
        self._robots_policy = robots_policy or RobotsPolicy(
            user_agent=config.user_agent,
            respect_robots_txt=config.respect_robots_txt,
        )
        self._client = httpx.AsyncClient(
            headers={"User-Agent": config.user_agent},
            timeout=config.request_timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._origin_locks: dict[str, asyncio.Lock] = {}
        self._last_request_times: dict[str, float] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    async def __aenter__(self) -> Self:
        """Enter the client context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close network resources when leaving the client context."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def fetch(
        self,
        url: str,
        *,
        depth: int = 0,
    ) -> httpx.Response:
        """Fetch an allowed URL or raise :class:`FetchError`."""
        response = await self._fetch_with_redirects(url, depth=depth)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise FetchError(
                f"HTTP {response.status_code} while fetching {url}"
            ) from error
        return response

    async def _fetch_with_redirects(
        self,
        url: str,
        *,
        depth: int,
    ) -> httpx.Response:
        """Fetch a URL while applying policies to every redirect target."""
        current_url = url
        for _ in range(MAX_REDIRECTS + 1):
            if not self._crawl_policy.allows(current_url, depth=depth):
                raise FetchError(
                    "URL is outside the permitted crawl scope: "
                    f"{current_url}"
                )

            rules = await self._robots_rules_for(current_url)
            if not self._robots_policy.allows(current_url, rules):
                raise FetchError(
                    f"robots.txt does not permit fetching: {current_url}"
                )

            response = await self._request_with_retries(current_url)
            if not response.is_redirect:
                return response

            location = response.headers.get("Location")
            if location is None:
                raise FetchError(
                    f"Redirect response has no Location header: {current_url}"
                )
            current_url = urljoin(str(response.url), location)

        raise FetchError(f"Too many redirects while fetching {url}")

    async def _request_with_retries(self, url: str) -> httpx.Response:
        """Perform a GET request and retry transient failures."""
        attempt = 0
        while True:
            try:
                response = await self._request_once(url)
            except httpx.RequestError as error:
                if attempt >= self._retry_policy.max_retries:
                    raise FetchError(
                        f"Failed to fetch {url}: {error}"
                    ) from error
                await asyncio.sleep(self._retry_policy.delay_for(attempt))
                attempt += 1
                continue

            if not self._retry_policy.should_retry(
                response.status_code,
                attempt,
            ):
                return response

            delay = self._retry_after_seconds(response)
            if delay is None:
                delay = self._retry_policy.delay_for(attempt)
            await asyncio.sleep(delay)
            attempt += 1

    async def _request_once(self, url: str) -> httpx.Response:
        """Rate-limit and perform one GET request."""
        await self._wait_for_rate_limit(url)
        async with self._semaphore:
            return await self._client.get(url)

    async def _wait_for_rate_limit(self, url: str) -> None:
        """Reserve the next request slot for a URL's origin."""
        origin = self._origin(url)
        lock = self._origin_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            now = monotonic()
            remaining = self._rate_limit_policy.delay_remaining(
                self._last_request_times.get(origin),
                now,
            )
            if remaining:
                await asyncio.sleep(remaining)
            self._last_request_times[origin] = monotonic()

    async def _robots_rules_for(
        self,
        url: str,
    ) -> RobotFileParser | None:
        """Return cached robots.txt rules for a URL's origin."""
        if not self._robots_policy.respect_robots_txt:
            return None

        origin = self._origin(url)
        if origin in self._robots_cache:
            return self._robots_cache[origin]

        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin not in self._robots_cache:
                self._robots_cache[origin] = await self._load_robots(origin)
        return self._robots_cache[origin]

    async def _load_robots(self, origin: str) -> RobotFileParser | None:
        """Retrieve and parse an origin's robots.txt file."""
        robots_url = f"{origin}/robots.txt"
        try:
            response = await self._request_with_retries(robots_url)
        except FetchError:
            return None

        parser = RobotFileParser()
        parser.set_url(robots_url)
        if response.status_code == httpx.codes.NOT_FOUND:
            parser.parse([])
            return parser
        if response.status_code in {
            httpx.codes.UNAUTHORIZED,
            httpx.codes.FORBIDDEN,
        }:
            parser.parse(["User-agent: *", "Disallow: /"])
            return parser
        if response.is_success:
            parser.parse(response.text.splitlines())
            return parser
        return None

    @staticmethod
    def _origin(url: str) -> str:
        """Return the normalized origin for a URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    def _retry_after_seconds(
        self,
        response: httpx.Response,
    ) -> float | None:
        """Parse and cap a Retry-After response header."""
        value = response.headers.get("Retry-After")
        if value is None:
            return None

        try:
            delay = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                delay = (retry_at - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None

        return min(
            max(0.0, delay),
            self._retry_policy.max_backoff_seconds,
        )
