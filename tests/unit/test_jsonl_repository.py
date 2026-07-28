"""Unit tests for JSON Lines page persistence."""

import json
from pathlib import Path

import pytest

from netskrape.extraction.models import ExtractedLink, ExtractedPage
from netskrape.storage.jsonl import JsonLinesPageRepository


@pytest.mark.asyncio
async def test_repository_appends_json_records(
    tmp_path: Path,
) -> None:
    """Pages and nested links are serialized as JSON Lines."""
    output = tmp_path / "nested" / "pages.jsonl"
    repository = JsonLinesPageRepository(output)
    page = ExtractedPage(
        url="https://example.com",
        status_code=200,
        title="Example",
        links=(
            ExtractedLink(
                url="https://example.com/about",
                rel=frozenset({"next", "external"}),
            ),
        ),
        content_type="text/html",
    )

    await repository.save(page)
    await repository.save_many((page,))

    records = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[0]["url"] == "https://example.com"
    assert records[0]["links"][0]["rel"] == ["external", "next"]
    assert records[0]["fetched_at"] == page.fetched_at.isoformat()


@pytest.mark.asyncio
async def test_repository_does_not_create_file_for_empty_batch(
    tmp_path: Path,
) -> None:
    """An empty batch performs no filesystem write."""
    output = tmp_path / "pages.jsonl"

    await JsonLinesPageRepository(output).save_many(())

    assert not output.exists()


def test_repository_rejects_directory_output(tmp_path: Path) -> None:
    """An existing directory cannot be used as an output file."""
    with pytest.raises(ValueError, match="must not be a directory"):
        JsonLinesPageRepository(tmp_path)
