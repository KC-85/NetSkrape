"""SQLAlchemy implementation of extracted-page persistence."""

from collections.abc import Iterable
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from netskrape.exceptions import StorageError
from netskrape.extraction.models import ExtractedLink, ExtractedPage
from netskrape.storage.database import Database
from netskrape.storage.tables import LinkRecord, PageRecord


class SQLAlchemyPageRepository:
    """Persist historical page snapshots with SQLAlchemy."""

    def __init__(self, database: Database) -> None:
        """Use sessions provided by an initialized database."""
        self._database = database

    async def save(self, page: ExtractedPage) -> None:
        """Persist one page snapshot."""
        await self.save_many((page,))

    async def save_many(
        self,
        pages: Iterable[ExtractedPage],
    ) -> None:
        """Persist a page batch in one transaction."""
        records = tuple(self._to_record(page) for page in pages)
        if not records:
            return

        try:
            async with self._database.sessions.begin() as session:
                session.add_all(records)
        except SQLAlchemyError as error:
            raise StorageError(
                f"Could not persist {len(records)} page snapshot(s)"
            ) from error

    async def all(self) -> tuple[ExtractedPage, ...]:
        """Return all stored snapshots in insertion order."""
        try:
            async with self._database.sessions() as session:
                result = await session.scalars(
                    select(PageRecord)
                    .options(selectinload(PageRecord.links))
                    .order_by(PageRecord.id)
                )
                records = result.unique().all()
        except SQLAlchemyError as error:
            raise StorageError(
                "Could not read stored page snapshots"
            ) from error

        return tuple(self._to_model(record) for record in records)

    @staticmethod
    def _to_record(page: ExtractedPage) -> PageRecord:
        """Convert an extraction model into related database records."""
        return PageRecord(
            url=page.url,
            status_code=page.status_code,
            title=page.title,
            text=page.text,
            content_type=page.content_type,
            fetched_at=page.fetched_at,
            links=[
                LinkRecord(
                    position=position,
                    url=link.url,
                    text=link.text,
                    title=link.title,
                    rel=sorted(link.rel),
                )
                for position, link in enumerate(page.links)
            ],
        )

    @staticmethod
    def _to_model(record: PageRecord) -> ExtractedPage:
        """Convert a database record into an extraction model."""
        fetched_at = record.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return ExtractedPage(
            url=record.url,
            status_code=record.status_code,
            title=record.title,
            text=record.text,
            links=tuple(
                ExtractedLink(
                    url=link.url,
                    text=link.text,
                    title=link.title,
                    rel=frozenset(link.rel),
                )
                for link in record.links
            ),
            content_type=record.content_type,
            fetched_at=fetched_at,
        )
