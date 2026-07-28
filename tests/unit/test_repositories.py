"""Tests for page repository contracts."""

import asyncio
from collections.abc import Iterable

import pytest

from netskrape.extraction.models import ExtractedPage
from netskrape.storage.repositories import (
    InMemoryPageRepository,
    PageRepository,
)


class RecordingRepository:
    """Minimal repository implementation used to verify the protocol."""

    def __init__(self) -> None:
        self.pages: list[ExtractedPage] = []

    async def save(self, page: ExtractedPage) -> None:
        """Record one page."""
        self.pages.append(page)

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Record multiple pages."""
        self.pages.extend(pages)


async def persist_pages(
    repository: PageRepository,
    pages: Iterable[ExtractedPage],
) -> None:
    """Exercise the repository through its public contract."""
    await repository.save_many(pages)


@pytest.mark.asyncio
async def test_repository_contract_accepts_compatible_implementation() -> None:
    """Repository implementations can be supplied structurally."""
    repository = RecordingRepository()
    first = ExtractedPage(url="https://example.com/1", status_code=200)
    second = ExtractedPage(url="https://example.com/2", status_code=200)

    await repository.save(first)
    await persist_pages(repository, [second])

    assert repository.pages == [first, second]


@pytest.mark.asyncio
async def test_in_memory_repository_preserves_historical_snapshots() -> None:
    """Repeated URLs remain separate crawl snapshots."""
    repository = InMemoryPageRepository()
    first = ExtractedPage(
        url="https://example.com",
        status_code=200,
        text="first",
    )
    second = ExtractedPage(
        url="https://example.com",
        status_code=200,
        text="second",
    )

    await repository.save(first)
    await repository.save(second)

    assert await repository.all() == (first, second)


@pytest.mark.asyncio
async def test_in_memory_repository_accepts_generator_batches() -> None:
    """Batch writes materialize one-shot iterables before storage."""
    repository = InMemoryPageRepository()
    pages = (
        ExtractedPage(
            url=f"https://example.com/{number}",
            status_code=200,
        )
        for number in range(3)
    )

    await repository.save_many(pages)

    assert len(await repository.all()) == 3


@pytest.mark.asyncio
async def test_in_memory_repository_supports_concurrent_writes() -> None:
    """Concurrent callers do not lose page snapshots."""
    repository = InMemoryPageRepository()
    pages = [
        ExtractedPage(
            url=f"https://example.com/{number}",
            status_code=200,
        )
        for number in range(10)
    ]

    await asyncio.gather(
        *(repository.save(page) for page in pages)
    )

    assert await repository.all() == tuple(pages)
