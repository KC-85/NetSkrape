"""Asynchronous SQLAlchemy engine and session lifecycle."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from netskrape.storage.tables import Base


class Database:
    """Own an asynchronous database engine and session factory."""

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
    ) -> None:
        """Create an asynchronous SQLAlchemy engine."""
        if not url.strip():
            raise ValueError("database URL must not be empty")
        self._engine: AsyncEngine = create_async_engine(url, echo=echo)
        self.sessions = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @classmethod
    def sqlite(
        cls,
        path: Path,
        *,
        echo: bool = False,
    ) -> "Database":
        """Create a database backed by a local SQLite file."""
        if path.exists() and path.is_dir():
            raise ValueError("SQLite database path must not be a directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        database = cls(
            f"sqlite+aiosqlite:///{path}",
            echo=echo,
        )

        @event.listens_for(database._engine.sync_engine, "connect")
        def enable_foreign_keys(
            dbapi_connection,
            connection_record,
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return database

    async def initialize(self) -> None:
        """Create missing application tables."""
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Close all pooled database connections."""
        await self._engine.dispose()
