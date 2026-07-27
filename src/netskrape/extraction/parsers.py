"""HTML parsing and content normalization."""

from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from netskrape.exceptions import ExtractionError
from netskrape.extraction.models import ExtractedLink, ExtractedPage


HTML_CONTENT_TYPES = frozenset(
    {"text/html", "application/xhtml+xml"}
)
NON_VISIBLE_TAGS = ("script", "style", "noscript", "template")
SUPPORTED_LINK_SCHEMES = frozenset({"http", "https"})


class HtmlParser:
    """Extract normalized page content from an HTTP response."""

    def __init__(self, *, parser_backend: str = "lxml") -> None:
        """Select the Beautiful Soup parser backend."""
        self._parser_backend = parser_backend

    def parse(self, response: httpx.Response) -> ExtractedPage:
        """Convert an HTML response into an :class:`ExtractedPage`."""
        content_type = self._content_type(response)
        if content_type not in HTML_CONTENT_TYPES:
            displayed_type = content_type or "missing"
            raise ExtractionError(
                f"Expected HTML content from {response.url}, "
                f"received {displayed_type}"
            )

        try:
            soup = BeautifulSoup(response.text, self._parser_backend)
            for element in soup.select(
                ",".join(NON_VISIBLE_TAGS)
            ):
                element.decompose()

            title = self._title(soup)
            links = self._links(soup, base_url=str(response.url))
            text = self._normalize_text(
                soup.get_text(separator=" ", strip=True)
            )
        except Exception as error:
            raise ExtractionError(
                f"Could not parse HTML from {response.url}: {error}"
            ) from error

        return ExtractedPage(
            url=str(response.url),
            status_code=response.status_code,
            title=title,
            text=text,
            links=links,
            content_type=content_type,
        )

    @staticmethod
    def _content_type(response: httpx.Response) -> str | None:
        """Return a normalized media type without header parameters."""
        value = response.headers.get("Content-Type")
        if value is None:
            return None
        return value.partition(";")[0].strip().lower()

    @classmethod
    def _title(cls, soup: BeautifulSoup) -> str | None:
        """Return the normalized document title."""
        if soup.title is None:
            return None
        title = cls._normalize_text(soup.title.get_text(" ", strip=True))
        return title or None

    @classmethod
    def _links(
        cls,
        soup: BeautifulSoup,
        *,
        base_url: str,
    ) -> tuple[ExtractedLink, ...]:
        """Extract unique, absolute HTTP links in document order."""
        links: list[ExtractedLink] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            raw_href = anchor.get("href")
            if not isinstance(raw_href, str):
                continue

            normalized_href = raw_href.strip()
            if not normalized_href:
                continue

            absolute_url, _ = urldefrag(
                urljoin(base_url, normalized_href)
            )
            parsed_url = urlparse(absolute_url)
            if (
                parsed_url.scheme.lower() not in SUPPORTED_LINK_SCHEMES
                or parsed_url.hostname is None
                or absolute_url in seen_urls
            ):
                continue

            seen_urls.add(absolute_url)
            raw_rel = anchor.get("rel")
            rel = (
                frozenset(str(value).lower() for value in raw_rel)
                if isinstance(raw_rel, list)
                else frozenset()
            )
            raw_title = anchor.get("title")
            title = (
                cls._normalize_text(raw_title)
                if isinstance(raw_title, str)
                else None
            )
            text = cls._normalize_text(
                anchor.get_text(separator=" ", strip=True)
            )
            links.append(
                ExtractedLink(
                    url=absolute_url,
                    text=text or None,
                    title=title or None,
                    rel=rel,
                )
            )

        return tuple(links)

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Collapse runs of whitespace into single spaces."""
        return " ".join(value.split())
