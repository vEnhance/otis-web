import os

import pytest

# Set Django settings module before any Django imports
# This is needed to support running `pytest --help` without Django errors
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "otisweb.settings")


def pytest_configure():
    """Set TESTING flag to True when running tests with pytest."""
    try:
        from django.conf import settings

        settings.TESTING = True
    except Exception:
        # Django not fully configured yet (e.g., when running pytest --help)
        # This is fine - TESTING will use its default value
        pass


@pytest.fixture
def otis(client):
    """
    Pytest fixture providing an enhanced test client with OTIS conveniences.

    Usage:
        def test_something(otis):
            otis.login(alice)
            resp = otis.get_20x("view-name", arg1, arg2)
            otis.assert_has(resp, "expected text")
    """
    # Import lazily to avoid loading Django during pytest --help
    from otisweb_testsuite.fixtures import OTISClient

    return OTISClient(client)
