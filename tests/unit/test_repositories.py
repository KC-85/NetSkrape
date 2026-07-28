"""Tests for page repository contracts."""

from collections.abc import Iterable

import pytest

from netskrape.extraction.models import ExtractedPage
from netskrape.storage.repositories import PageRepository


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
