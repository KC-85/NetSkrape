"""Smoke tests for the package skeleton."""

import netskrape


def test_package_exposes_version() -> None:
    """The installed package exposes its public version."""
    assert netskrape.__version__ == "0.1.0"
