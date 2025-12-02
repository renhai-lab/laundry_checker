"""Helper utilities for the Laundry Checker integration."""

from __future__ import annotations


def normalize_api_host(api_host: str) -> str:
    """Return a normalized QWeather API host with scheme and without trailing slash."""
    host = (api_host or "").strip()
    if not host:
        raise ValueError("QWeather API host cannot be empty")

    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"

    return host.rstrip("/")