"""Application logging configuration and safe value formatting."""

import logging
import sys
from typing import TextIO
from urllib.parse import urlsplit, urlunsplit

from netskrape.config import LogLevel


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    *,
    stream: TextIO | None = None,
) -> None:
    """Configure application logging for command-line execution."""
    logging.basicConfig(
        level=level.value,
        format=LOG_FORMAT,
        stream=stream or sys.stderr,
        force=True,
    )


def safe_url(url: str) -> str:
    """Remove credentials, query values, and fragments from a URL for logs."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            return "<invalid-url>"

        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        query = "<redacted>" if parsed.query else ""
        return urlunsplit(
            (
                parsed.scheme,
                f"{hostname}{port}",
                parsed.path,
                query,
                "",
            )
        )
    except ValueError:
        return "<invalid-url>"
