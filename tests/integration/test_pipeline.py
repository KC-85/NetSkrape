"""End-to-end tests for the scraping pipeline."""

import json
from pathlib import Path

import httpx
import pytest

from netskrape.config import ScraperConfig
from netskrape.crawling.client import ScraperClient
from netskrape.crawling.policies import CrawlPolicy
from netskrape.crawling.scheduler import CrawlScheduler
from netskrape.extraction.parsers import HtmlParser
from netskrape.scraper import Scraper
from netskrape.storage.jsonl import JsonLinesPageRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_pipeline_respects_robots_and_persists_pages(
    tmp_path: Path,
) -> None:
    """Real components crawl a controlled site without internet access."""
    requested_paths: list[str] = []

    async def site(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        responses = {
            "/robots.txt": httpx.Response(
                200,
                headers={"Content-Type": "text/plain"},
                text=(
                    "User-agent: NetSkrape\n"
                    "Disallow: /private\n"
                ),
            ),
            "/": httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                text=(
                    "<html><head><title>Home</title></head><body>"
                    '<a href="/about">About</a>'
                    '<a href="/about#team">About again</a>'
                    '<a href="/private">Private</a>'
                    "</body></html>"
                ),
            ),
            "/about": httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                text=(
                    "<html><head><title>About</title></head>"
                    "<body><p>About NetSkrape</p></body></html>"
                ),
            ),
        }
        return responses.get(
            request.url.path,
            httpx.Response(404),
        )

    output = tmp_path / "crawl" / "pages.jsonl"
    config = ScraperConfig(
        max_concurrency=2,
        requests_per_second=1_000_000,
        max_retries=0,
        respect_robots_txt=True,
    )
    crawl_policy = CrawlPolicy(
        allowed_domains=frozenset({"example.com"}),
        max_depth=2,
    )

    async with ScraperClient(
        config,
        crawl_policy=crawl_policy,
        transport=httpx.MockTransport(site),
    ) as client:
        scheduler = CrawlScheduler(
            client,
            HtmlParser(),
            worker_count=2,
            max_pages=10,
            max_depth=2,
        )
        result = await Scraper(
            scheduler,
            JsonLinesPageRepository(output),
        ).run(["https://example.com/"])

    assert {page.url for page in result.pages} == {
        "https://example.com/",
        "https://example.com/about",
    }
    assert {page.title for page in result.pages} == {"Home", "About"}
    assert len(result.failures) == 1
    assert result.failures[0].url == "https://example.com/private"
    assert result.failures[0].error_type == "FetchError"

    assert requested_paths.count("/robots.txt") == 1
    assert requested_paths.count("/about") == 1
    assert "/private" not in requested_paths

    records = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert {record["url"] for record in records} == {
        "https://example.com/",
        "https://example.com/about",
    }
