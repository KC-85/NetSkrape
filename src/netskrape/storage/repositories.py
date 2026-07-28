"""Persistence contracts for extracted pages."""

import asyncio
from collections.abc import Iterable
from typing import Protocol

from netskrape.extraction.models import ExtractedPage


class PageRepository(Protocol):
    """Persistence contract for extracted pages."""

    async def save(self, page: ExtractedPage) -> None:
        """Persist one extracted page."""
        ...

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Persist multiple extracted pages."""
        ...


class InMemoryPageRepository:
    """Store every extracted page as an in-memory crawl snapshot."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._pages: list[ExtractedPage] = []
        self._lock = asyncio.Lock()

    async def save(self, page: ExtractedPage) -> None:
        """Store one page."""
        async with self._lock:
            self._pages.append(page)

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Store a batch atomically while preserving input order."""
        batch = tuple(pages)
        async with self._lock:
            self._pages.extend(batch)

    async def all(self) -> tuple[ExtractedPage, ...]:
        """Return an immutable snapshot in insertion order."""
        async with self._lock:
            return tuple(self._pages)
