"""JSON Lines persistence for extracted pages."""

import asyncio
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from netskrape.exceptions import StorageError
from netskrape.extraction.models import ExtractedLink, ExtractedPage


logger = logging.getLogger(__name__)


class JsonLinesPageRepository:
    """Append extracted pages to a UTF-8 JSON Lines file."""

    def __init__(self, path: Path) -> None:
        """Configure the output file."""
        if path.exists() and path.is_dir():
            raise ValueError("JSON Lines output path must not be a directory")
        self._path = path
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        """Return the configured output path."""
        return self._path

    async def save(self, page: ExtractedPage) -> None:
        """Append one extracted page."""
        await self.save_many((page,))

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Append a batch of extracted pages in input order."""
        lines = tuple(
            json.dumps(
                self._page_record(page),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for page in pages
        )
        if not lines:
            return

        async with self._lock:
            try:
                self._append_lines(lines)
            except OSError as error:
                raise StorageError(
                    f"Could not write crawl output to {self._path}: {error}"
                ) from error
        logger.info(
            "Appended %d page record(s) to %s",
            len(lines),
            self._path,
        )

    def _append_lines(self, lines: tuple[str, ...]) -> None:
        """Perform one locked append operation."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as output:
            output.write("\n".join(lines))
            output.write("\n")

    @classmethod
    def _page_record(cls, page: ExtractedPage) -> dict[str, Any]:
        """Convert a page into a JSON-compatible record."""
        return {
            "url": page.url,
            "status_code": page.status_code,
            "title": page.title,
            "text": page.text,
            "links": [
                cls._link_record(link)
                for link in page.links
            ],
            "content_type": page.content_type,
            "fetched_at": page.fetched_at.isoformat(),
        }

    @staticmethod
    def _link_record(link: ExtractedLink) -> dict[str, Any]:
        """Convert a link into a JSON-compatible record."""
        return {
            "url": link.url,
            "text": link.text,
            "title": link.title,
            "rel": sorted(link.rel),
        }
