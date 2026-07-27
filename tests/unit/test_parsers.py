"""Unit tests for HTML extraction."""

import httpx
import pytest

from netskrape.exceptions import ExtractionError
from netskrape.extraction.parsers import HtmlParser


def make_response(
    html: str,
    *,
    content_type: str = "text/html; charset=utf-8",
) -> httpx.Response:
    """Create an HTTP response with a final request URL."""
    request = httpx.Request("GET", "https://example.com/docs/index.html")
    return httpx.Response(
        200,
        headers={"Content-Type": content_type},
        text=html,
        request=request,
    )


def test_parse_extracts_normalized_page_content() -> None:
    response = make_response(
        """
        <html>
          <head>
            <title> NetSkrape   Guide </title>
            <style>.hidden { display: none; }</style>
          </head>
          <body>
            <h1>Getting   started</h1>
            <script>doNotInclude()</script>
            <a href="/about#team" title=" About us " rel="nofollow external">
              About <strong>us</strong>
            </a>
          </body>
        </html>
        """
    )

    page = HtmlParser().parse(response)

    assert page.url == "https://example.com/docs/index.html"
    assert page.status_code == 200
    assert page.content_type == "text/html"
    assert page.title == "NetSkrape Guide"
    assert page.text == "NetSkrape Guide Getting started About us"
    assert len(page.links) == 1
    assert page.links[0].url == "https://example.com/about"
    assert page.links[0].text == "About us"
    assert page.links[0].title == "About us"
    assert page.links[0].rel == frozenset({"nofollow", "external"})


def test_parse_deduplicates_links_and_filters_unsupported_schemes() -> None:
    response = make_response(
        """
        <a href="/page#first">First</a>
        <a href="/page#second">Duplicate</a>
        <a href="mailto:user@example.com">Email</a>
        <a href="javascript:void(0)">Script</a>
        <a href="">Empty</a>
        """
    )

    page = HtmlParser().parse(response)

    assert [link.url for link in page.links] == [
        "https://example.com/page",
    ]


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "text/plain", ""],
)
def test_parse_rejects_non_html_content(content_type: str) -> None:
    response = make_response("not html", content_type=content_type)

    with pytest.raises(ExtractionError, match="Expected HTML"):
        HtmlParser().parse(response)


def test_parse_accepts_xhtml_content() -> None:
    response = make_response(
        "<html><body><p>Content</p></body></html>",
        content_type="application/xhtml+xml",
    )

    assert HtmlParser().parse(response).text == "Content"
