"""
OTIS-WEB Test Suite Utilities

This package provides test helpers and base classes for Django testing,
with enhanced assertion methods and debugging capabilities.
"""

__all__ = ["EvanTestCase", "UniqueFaker"]
__version__ = "1.0.0"


def __getattr__(name: str):
    """Lazy import to avoid loading Django dependencies during pytest --help."""
    if name == "EvanTestCase":
        from .testcase import EvanTestCase

        return EvanTestCase
    if name == "UniqueFaker":
        from .testcase import UniqueFaker

        return UniqueFaker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
