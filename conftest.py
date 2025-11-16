import pytest
from django.conf import settings


def pytest_configure():
    """Set TESTING flag to True when running tests with pytest."""
    settings.TESTING = True
