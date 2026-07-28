"""High-level scraping orchestration."""

import logging
from collections.abc import Iterable
from typing import Protocol

from netskrape.crawling.scheduler import CrawlResult
from netskrape.storage.repositories import PageRepository


logger = logging.getLogger(__name__)


class Scheduler(Protocol):
    """Crawl scheduler contract required by the orchestrator."""

    async def crawl(self, seed_urls: Iterable[str]) -> CrawlResult:
        """Crawl seed URLs and return their result."""
        ...


class Scraper:
    """Coordinate crawling and persistence."""

    def __init__(
        self,
        scheduler: Scheduler,
        repository: PageRepository,
    ) -> None:
        """Configure orchestration dependencies."""
        self._scheduler = scheduler
        self._repository = repository

    async def run(
        self,
        seed_urls: Iterable[str],
    ) -> CrawlResult:
        """Crawl seed URLs and persist successful pages."""
        result = await self._scheduler.crawl(seed_urls)

        if result.pages:
            logger.info("Persisting %d extracted page(s)", len(result.pages))
            await self._repository.save_many(result.pages)

        return result
