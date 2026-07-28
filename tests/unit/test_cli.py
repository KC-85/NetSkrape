"""Unit tests for the command-line interface."""

from pathlib import Path

from click.testing import CliRunner

from netskrape import cli
from netskrape.crawling.scheduler import CrawlFailure, CrawlResult
from netskrape.extraction.models import ExtractedPage


def test_crawl_command_reports_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A successful crawl reports persisted page totals."""
    output = tmp_path / "pages.jsonl"

    async def fake_run_crawl(*args, **kwargs) -> CrawlResult:
        return CrawlResult(
            pages=(
                ExtractedPage(
                    url="https://example.com",
                    status_code=200,
                ),
            ),
            failures=(),
        )

    monkeypatch.setattr(cli, "_run_crawl", fake_run_crawl)

    result = CliRunner().invoke(
        cli.main,
        ["crawl", "https://example.com", "--output", str(output)],
    )

    assert result.exit_code == cli.SUCCESS
    assert "1 page(s), 0 failure(s)" in result.output
    assert f"Results appended to {output}" in result.output


def test_crawl_command_reports_partial_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Individual crawl failures produce the documented partial exit code."""
    failure = CrawlFailure(
        url="https://example.com/missing",
        depth=1,
        error="not found",
        error_type="FetchError",
    )

    async def fake_run_crawl(*args, **kwargs) -> CrawlResult:
        return CrawlResult(pages=(), failures=(failure,))

    monkeypatch.setattr(cli, "_run_crawl", fake_run_crawl)

    result = CliRunner().invoke(
        cli.main,
        ["crawl", "https://example.com"],
    )

    assert result.exit_code == cli.PARTIAL_FAILURE
    assert "0 page(s), 1 failure(s)" in result.output
    assert "FetchError" in result.output


def test_seed_domains_rejects_relative_urls() -> None:
    """CLI seed URLs must include an HTTP scheme and hostname."""
    try:
        cli._seed_domains(("/relative",))
    except ValueError as error:
        assert "absolute HTTP(S)" in str(error)
    else:
        raise AssertionError("relative seed URL was accepted")


def test_main_help_lists_crawl_command() -> None:
    """The top-level help exposes the crawl command."""
    result = CliRunner().invoke(cli.main, ["--help"])

    assert result.exit_code == 0
    assert "crawl" in result.output
