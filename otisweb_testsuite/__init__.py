"""
OTIS-WEB Test Suite Utilities

This package provides test helpers and base classes for Django testing,
with enhanced assertion methods and debugging capabilities.
"""

from .faker import UniqueFaker

__all__ = ["UniqueFaker"]
__version__ = "1.0.0"
