"""SQLAlchemy table mappings for extracted page snapshots."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for NetSkrape database mappings."""


class PageRecord(Base):
    """Historical snapshot of one extracted page."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    links: Mapped[list["LinkRecord"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="LinkRecord.position",
        lazy="selectin",
    )


class LinkRecord(Base):
    """Link discovered within a page snapshot."""

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    rel: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    page: Mapped[PageRecord] = relationship(back_populates="links")
