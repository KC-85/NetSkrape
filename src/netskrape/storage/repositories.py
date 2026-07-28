"""Persistence contracts for extracted pages."""

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
