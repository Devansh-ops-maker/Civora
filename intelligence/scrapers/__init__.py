"""Scrapers package for SIH 2026 intelligence app."""

from typing import Any

__all__ = [
    "StartupIndiaScraper",
    "get_startup_schemes",
    "get_startup_schemes_json",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import startup_india
        return getattr(startup_india, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
