"""Unit tests for extraction models."""

from dataclasses import FrozenInstanceError

import pytest

from netskrape.extraction.models import ExtractedLink, ExtractedPage


def test_extracted_page_has_safe_defaults() -> None:
    """Optional page content uses immutable, predictable defaults."""
    page = ExtractedPage(url="https://example.com", status_code=200)

    assert page.text == ""
    assert page.links == ()
    assert page.content_type is None
    assert page.fetched_at.tzinfo is not None


def test_fetched_at_is_created_for_each_page() -> None:
    """Each page receives its own timestamp from the default factory."""
    first = ExtractedPage(url="https://example.com/1", status_code=200)
    second = ExtractedPage(url="https://example.com/2", status_code=200)

    assert first.fetched_at is not second.fetched_at
    assert first.fetched_at <= second.fetched_at


def test_extraction_models_are_immutable() -> None:
    """Extracted values cannot be changed after construction."""
    link = ExtractedLink(url="https://example.com/page")

    with pytest.raises(FrozenInstanceError):
        link.url = "https://example.net"  # type: ignore[misc]
