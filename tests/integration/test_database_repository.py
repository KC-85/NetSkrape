"""Integration tests for SQLAlchemy page persistence."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from netskrape.extraction.models import ExtractedLink, ExtractedPage
from netskrape.storage.database import Database
from netskrape.storage.sqlalchemy import SQLAlchemyPageRepository
from netskrape.storage.tables import LinkRecord, PageRecord


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlalchemy_repository_preserves_page_history_and_links(
    tmp_path: Path,
) -> None:
    """Repeated URLs and ordered links are stored as separate snapshots."""
    database_path = tmp_path / "nested" / "netskrape.db"
    database = Database.sqlite(database_path)
    await database.initialize()
    repository = SQLAlchemyPageRepository(database)
    first = ExtractedPage(
        url="https://example.com",
        status_code=200,
        title="First",
        text="original",
        links=(
            ExtractedLink(
                url="https://example.com/about",
                text="About",
                rel=frozenset({"next", "external"}),
            ),
            ExtractedLink(
                url="https://example.com/contact",
                text="Contact",
            ),
        ),
        content_type="text/html",
    )
    second = ExtractedPage(
        url="https://example.com",
        status_code=200,
        title="Second",
        text="updated",
        content_type="text/html",
    )

    try:
        await repository.save(first)
        await repository.save_many((second,))

        snapshots = await repository.all()
        async with database.sessions() as session:
            page_count = await session.scalar(
                select(func.count()).select_from(PageRecord)
            )
            link_count = await session.scalar(
                select(func.count()).select_from(LinkRecord)
            )
    finally:
        await database.dispose()

    assert database_path.exists()
    assert snapshots == (first, second)
    assert page_count == 2
    assert link_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlalchemy_repository_ignores_empty_batch(
    tmp_path: Path,
) -> None:
    """An empty batch leaves an initialized database unchanged."""
    database = Database.sqlite(tmp_path / "netskrape.db")
    await database.initialize()
    repository = SQLAlchemyPageRepository(database)

    try:
        await repository.save_many(())
        assert await repository.all() == ()
    finally:
        await database.dispose()


def test_database_rejects_directory_path(tmp_path: Path) -> None:
    """A SQLite database path must identify a file."""
    with pytest.raises(ValueError, match="must not be a directory"):
        Database.sqlite(tmp_path)
