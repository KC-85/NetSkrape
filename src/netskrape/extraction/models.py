"""Models for extracted and normalized data."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ExtractedLink:
    """A link extracted from a web page."""

    url: str
    text: str | None = None
    title: str | None = None
    rel: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Normalized content extracted from a web page."""

    url: str
    status_code: int
    title: str | None = None
    text: str = ""
    links: tuple[ExtractedLink, ...] = ()
    content_type: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
