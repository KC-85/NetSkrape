"""Unit tests for asynchronous crawl scheduling."""

from collections.abc import Mapping

import httpx
import pytest

from netskrape.crawling.scheduler import CrawlScheduler
from netskrape.exceptions import FetchError
from netskrape.extraction.parsers import HtmlParser


class FakeClient:
    """Return in-memory responses for known URLs."""

    def __init__(
        self,
        pages: Mapping[str, str | Exception],
    ) -> None:
        self._pages = pages
        self.requests: list[tuple[str, int]] = []

    async def fetch(
        self,
        url: str,
        *,
        depth: int = 0,
    ) -> httpx.Response:
        """Return a configured response or raise its configured error."""
        self.requests.append((url, depth))
        content = self._pages[url]
        if isinstance(content, Exception):
            raise content
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=content,
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_scheduler_discovers_links_and_deduplicates_urls() -> None:
    client = FakeClient(
        {
            "https://example.com": (
                '<a href="/one#section">One</a>'
                '<a href="/one">Duplicate</a>'
            ),
            "https://example.com/one": "<p>Done</p>",
        }
    )
    scheduler = CrawlScheduler(
        client,
        HtmlParser(),
        worker_count=2,
    )

    result = await scheduler.crawl(
        ["https://example.com", "https://example.com#top"]
    )

    assert {page.url for page in result.pages} == {
        "https://example.com",
        "https://example.com/one",
    }
    assert result.failures == ()
    assert sorted(client.requests) == [
        ("https://example.com", 0),
        ("https://example.com/one", 1),
    ]


@pytest.mark.asyncio
async def test_scheduler_enforces_maximum_depth() -> None:
    client = FakeClient(
        {
            "https://example.com": '<a href="/one">One</a>',
            "https://example.com/one": '<a href="/two">Two</a>',
        }
    )
    scheduler = CrawlScheduler(
        client,
        HtmlParser(),
        max_depth=1,
    )

    result = await scheduler.crawl(["https://example.com"])

    assert len(result.pages) == 2
    assert [url for url, _ in client.requests] == [
        "https://example.com",
        "https://example.com/one",
    ]


@pytest.mark.asyncio
async def test_scheduler_prevents_work_beyond_page_limit() -> None:
    client = FakeClient(
        {
            "https://example.com": (
                '<a href="/one">One</a>'
                '<a href="/two">Two</a>'
                '<a href="/three">Three</a>'
            ),
            "https://example.com/one": "<p>One</p>",
        }
    )
    scheduler = CrawlScheduler(
        client,
        HtmlParser(),
        max_pages=2,
    )

    result = await scheduler.crawl(["https://example.com"])

    assert len(result.pages) == 2
    assert len(client.requests) == 2


@pytest.mark.asyncio
async def test_scheduler_collects_failure_and_continues() -> None:
    client = FakeClient(
        {
            "https://example.com/fails": FetchError("unavailable"),
            "https://example.com/works": "<p>Works</p>",
        }
    )
    scheduler = CrawlScheduler(
        client,
        HtmlParser(),
        worker_count=2,
    )

    result = await scheduler.crawl(
        [
            "https://example.com/fails",
            "https://example.com/works",
        ]
    )

    assert [page.url for page in result.pages] == [
        "https://example.com/works"
    ]
    assert len(result.failures) == 1
    assert result.failures[0].error == "unavailable"
    assert result.failures[0].error_type == "FetchError"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"worker_count": 0}, "worker_count"),
        ({"max_pages": 0}, "max_pages"),
        ({"max_depth": -1}, "max_depth"),
    ],
)
def test_scheduler_rejects_invalid_limits(
    arguments: dict[str, int],
    message: str,
) -> None:
    client = FakeClient({})

    with pytest.raises(ValueError, match=message):
        CrawlScheduler(
            client,
            HtmlParser(),
            **arguments,
        )
