"""Command-line interface and application composition."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

import click

from netskrape.config import ScraperConfig
from netskrape.crawling.client import ScraperClient
from netskrape.crawling.policies import CrawlPolicy
from netskrape.crawling.scheduler import CrawlResult, CrawlScheduler
from netskrape.exceptions import NetSkrapeError
from netskrape.extraction.parsers import HtmlParser
from netskrape.logging import configure_logging
from netskrape.scraper import Scraper
from netskrape.storage.jsonl import JsonLinesPageRepository


SUCCESS = 0
RUNTIME_ERROR = 1
PARTIAL_FAILURE = 3

logger = logging.getLogger(__name__)


@click.group()
def main() -> None:
    """Crawl web pages safely and save normalized results."""


@main.command()
@click.argument("seed_urls", nargs=-1, required=True)
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path("netskrape-results.jsonl"),
    show_default=True,
    help="Append extracted pages to this JSON Lines file.",
)
@click.option(
    "--database",
    "database_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Store pages in this SQLite database instead of JSON Lines.",
)
@click.option(
    "--max-pages",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
)
@click.option(
    "--max-depth",
    type=click.IntRange(min=0),
    default=3,
    show_default=True,
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
)
def crawl(
    seed_urls: tuple[str, ...],
    output: Path,
    database_path: Path | None,
    max_pages: int,
    max_depth: int,
    workers: int,
) -> None:
    """Crawl one or more SEED_URLS and persist successful pages."""
    try:
        result = asyncio.run(
            _run_crawl(
                seed_urls,
                output=output,
                database_path=database_path,
                max_pages=max_pages,
                max_depth=max_depth,
                workers=workers,
            )
        )
    except (NetSkrapeError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(
        f"Crawl complete: {len(result.pages)} page(s), "
        f"{len(result.failures)} failure(s)."
    )
    if result.pages:
        if database_path is not None:
            click.echo(f"Results saved to SQLite database {database_path}.")
        else:
            click.echo(f"Results appended to {output}.")
    for failure in result.failures:
        click.echo(
            f"{failure.url} [{failure.error_type}]: {failure.error}",
            err=True,
        )

    if result.failures:
        raise click.exceptions.Exit(PARTIAL_FAILURE)
    raise click.exceptions.Exit(SUCCESS)


async def _run_crawl(
    seed_urls: tuple[str, ...],
    *,
    output: Path,
    database_path: Path | None,
    max_pages: int,
    max_depth: int,
    workers: int,
) -> CrawlResult:
    """Construct concrete components and run one crawl."""
    allowed_domains = _seed_domains(seed_urls)
    config = ScraperConfig.from_env()
    configure_logging(config.log_level)
    logger.info(
        "Starting crawl with %d seed(s), %d worker(s), "
        "maximum %d page(s), and depth %d",
        len(seed_urls),
        workers,
        max_pages,
        max_depth,
    )
    crawl_policy = CrawlPolicy(
        allowed_domains=allowed_domains,
        max_depth=max_depth,
    )
    database = None
    if database_path is None:
        repository = JsonLinesPageRepository(output)
    else:
        from netskrape.storage.database import Database
        from netskrape.storage.sqlalchemy import SQLAlchemyPageRepository

        database = Database.sqlite(database_path)
        await database.initialize()
        repository = SQLAlchemyPageRepository(database)

    try:
        async with ScraperClient(
            config,
            crawl_policy=crawl_policy,
        ) as client:
            scheduler = CrawlScheduler(
                client,
                HtmlParser(),
                worker_count=workers,
                max_pages=max_pages,
                max_depth=max_depth,
            )
            return await Scraper(scheduler, repository).run(seed_urls)
    finally:
        if database is not None:
            await database.dispose()


def _seed_domains(seed_urls: tuple[str, ...]) -> frozenset[str]:
    """Validate seed URLs and return their normalized hostnames."""
    domains: set[str] = set()
    for seed_url in seed_urls:
        parsed = urlparse(seed_url)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or parsed.hostname is None
        ):
            raise ValueError(
                f"Seed URL must be an absolute HTTP(S) URL: {seed_url}"
            )
        domains.add(parsed.hostname.lower().rstrip("."))
    return frozenset(domains)
