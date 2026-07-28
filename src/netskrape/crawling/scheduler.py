"""Asynchronous crawl scheduling and traversal."""

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urldefrag

import httpx

from netskrape.extraction.models import ExtractedPage
from netskrape.logging import safe_url


logger = logging.getLogger(__name__)


class PageClient(Protocol):
    """Interface required from a scheduler HTTP client."""

    async def fetch(
        self,
        url: str,
        *,
        depth: int = 0,
    ) -> httpx.Response:
        """Fetch one page."""


class PageParser(Protocol):
    """Interface required from a scheduler response parser."""

    def parse(self, response: httpx.Response) -> ExtractedPage:
        """Extract one fetched page."""


@dataclass(frozen=True, slots=True)
class CrawlRequest:
    """A URL and its traversal depth."""

    url: str
    depth: int = 0

    def __post_init__(self) -> None:
        """Validate the request."""
        if not self.url.strip():
            raise ValueError("url must not be empty")
        if self.depth < 0:
            raise ValueError("depth must not be negative")


@dataclass(frozen=True, slots=True)
class CrawlFailure:
    """A request that could not be fetched or extracted."""

    url: str
    depth: int
    error: str
    error_type: str


@dataclass(frozen=True, slots=True)
class CrawlResult:
    """Successful pages and failures produced by a crawl."""

    pages: tuple[ExtractedPage, ...]
    failures: tuple[CrawlFailure, ...]


class _Stop:
    """Worker shutdown sentinel."""


_STOP = _Stop()


class CrawlScheduler:
    """Traverse pages with a bounded set of asynchronous workers."""

    def __init__(
        self,
        client: PageClient,
        parser: PageParser,
        *,
        worker_count: int = 5,
        max_pages: int = 100,
        max_depth: int = 3,
    ) -> None:
        """Configure scheduler dependencies and crawl limits."""
        if worker_count <= 0:
            raise ValueError("worker_count must be greater than zero")
        if max_pages <= 0:
            raise ValueError("max_pages must be greater than zero")
        if max_depth < 0:
            raise ValueError("max_depth must not be negative")

        self._client = client
        self._parser = parser
        self._worker_count = worker_count
        self._max_pages = max_pages
        self._max_depth = max_depth

    async def crawl(self, seed_urls: Iterable[str]) -> CrawlResult:
        """Crawl seeds and discovered links within configured limits."""
        if isinstance(seed_urls, str):
            raise TypeError("seed_urls must be an iterable of URL strings")

        queue: asyncio.Queue[CrawlRequest | _Stop] = asyncio.Queue()
        seen_urls: set[str] = set()
        pages: list[ExtractedPage] = []
        failures: list[CrawlFailure] = []

        def schedule(url: str, depth: int) -> bool:
            normalized_url = self._normalize_url(url)
            if (
                not normalized_url
                or depth > self._max_depth
                or normalized_url in seen_urls
                or len(seen_urls) >= self._max_pages
            ):
                return False

            seen_urls.add(normalized_url)
            queue.put_nowait(
                CrawlRequest(url=normalized_url, depth=depth)
            )
            return True

        for seed_url in seed_urls:
            if not isinstance(seed_url, str):
                raise TypeError("every seed URL must be a string")
            schedule(seed_url, depth=0)

        logger.info("Scheduled %d unique seed URL(s)", queue.qsize())

        async def worker() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is _STOP:
                        return

                    try:
                        response = await self._client.fetch(
                            item.url,
                            depth=item.depth,
                        )
                        page = self._parser.parse(response)
                    except Exception as error:
                        logger.warning(
                            "Crawl failed for %s at depth %d: %s",
                            safe_url(item.url),
                            item.depth,
                            type(error).__name__,
                        )
                        failures.append(
                            CrawlFailure(
                                url=item.url,
                                depth=item.depth,
                                error=str(error),
                                error_type=type(error).__name__,
                            )
                        )
                        continue

                    pages.append(page)
                    next_depth = item.depth + 1
                    if next_depth <= self._max_depth:
                        for link in page.links:
                            schedule(link.url, next_depth)
                finally:
                    queue.task_done()

        workers = [
            asyncio.create_task(
                worker(),
                name=f"netskrape-worker-{number}",
            )
            for number in range(self._worker_count)
        ]

        try:
            await queue.join()
        finally:
            for _ in workers:
                queue.put_nowait(_STOP)
            await asyncio.gather(*workers)

        result = CrawlResult(
            pages=tuple(pages),
            failures=tuple(failures),
        )
        logger.info(
            "Crawl finished with %d page(s) and %d failure(s)",
            len(result.pages),
            len(result.failures),
        )
        return result

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip whitespace and fragments for queue deduplication."""
        normalized_url, _ = urldefrag(url.strip())
        return normalized_url
