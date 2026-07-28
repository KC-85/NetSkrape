"""Unit tests for high-level scraper orchestration."""

from collections.abc import Iterable

import pytest

from netskrape.crawling.scheduler import CrawlFailure, CrawlResult
from netskrape.extraction.models import ExtractedPage
from netskrape.scraper import Scraper
from netskrape.storage.repositories import InMemoryPageRepository


class StubScheduler:
    """Return a predefined crawl result and record supplied seeds."""

    def __init__(self, result: CrawlResult) -> None:
        self._result = result
        self.seed_urls: tuple[str, ...] = ()

    async def crawl(self, seed_urls: Iterable[str]) -> CrawlResult:
        """Return the configured result."""
        self.seed_urls = tuple(seed_urls)
        return self._result


class FailingRepository(InMemoryPageRepository):
    """Repository that simulates a persistence failure."""

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Fail instead of persisting the pages."""
        raise RuntimeError("storage unavailable")


@pytest.mark.asyncio
async def test_run_persists_successful_pages_and_returns_result() -> None:
    """Successful pages are persisted without changing the crawl result."""
    page = ExtractedPage(url="https://example.com", status_code=200)
    result = CrawlResult(pages=(page,), failures=())
    scheduler = StubScheduler(result)
    repository = InMemoryPageRepository()
    scraper = Scraper(scheduler, repository)

    returned = await scraper.run(["https://example.com"])

    assert returned is result
    assert scheduler.seed_urls == ("https://example.com",)
    assert await repository.all() == (page,)


@pytest.mark.asyncio
async def test_run_returns_failures_but_only_persists_pages() -> None:
    """Crawl failures remain reportable and are never sent to storage."""
    page = ExtractedPage(url="https://example.com", status_code=200)
    failure = CrawlFailure(
        url="https://example.com/missing",
        depth=1,
        error="not found",
        error_type="FetchError",
    )
    result = CrawlResult(pages=(page,), failures=(failure,))
    repository = InMemoryPageRepository()

    returned = await Scraper(
        StubScheduler(result),
        repository,
    ).run(["https://example.com"])

    assert returned.failures == (failure,)
    assert await repository.all() == (page,)


@pytest.mark.asyncio
async def test_run_does_not_write_an_empty_result() -> None:
    """An empty crawl completes without requiring a repository write."""
    result = CrawlResult(pages=(), failures=())
    repository = FailingRepository()

    returned = await Scraper(
        StubScheduler(result),
        repository,
    ).run([])

    assert returned is result


@pytest.mark.asyncio
async def test_run_propagates_repository_failures() -> None:
    """Persistence errors are not misreported as crawl failures."""
    page = ExtractedPage(url="https://example.com", status_code=200)
    scraper = Scraper(
        StubScheduler(CrawlResult(pages=(page,), failures=())),
        FailingRepository(),
    )

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await scraper.run(["https://example.com"])
