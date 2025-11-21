from django.conf import settings

# Import and register the OTIS fixtures
pytest_plugins = ["otisweb_testsuite.fixtures"]


def pytest_configure():
    """Set TESTING flag to True when running tests with pytest."""
    try:
        settings.TESTING = True
    except Exception:
        # Django not fully configured yet (e.g., when running pytest --help)
        # This is fine - TESTING will use its default value
        pass
