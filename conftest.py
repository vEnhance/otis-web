import os

import django
from django.conf import settings

# Set Django settings module before any Django imports
# This is needed because pytest_plugins is processed before pyproject.toml settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "otisweb.settings")
django.setup()

# Import and register the OTIS fixtures
pytest_plugins = ["otisweb_testsuite.fixtures"]


def pytest_configure():
    settings.TESTING = True
