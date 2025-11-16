from django.conf import settings

# Import and register the OTIS fixtures
pytest_plugins = ["otisweb_testsuite.fixtures"]


def pytest_configure():
    """Set TESTING flag to True when running tests with pytest."""
    settings.TESTING = True
