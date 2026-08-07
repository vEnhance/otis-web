import logging
import os

import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import Resolver404, resolve
from django.utils.log import log_response

from core.factories import UserFactory
from otisweb.settings import fix_response_location


@pytest.mark.django_db
def test_registration(otis):
    otis.get_20x("account_signup")
    otis.post_20x(
        "account_signup",
        data={
            "username": "alice",
            "email": "alice@evanchen.cc",
            "first_name": "Alice",
            "last_name": "Aardvark",
            "password1": "this_password_isnt_a_puzzle_but_nice_try",
            "password2": "this_password_isnt_a_puzzle_but_nice_try",
        },
        follow=True,
    )
    otis.login("alice")


@pytest.mark.django_db
def test_social_page(otis):
    UserFactory.create(username="evan")
    otis.login("evan")
    otis.get_20x("socialaccount_connections")


@pytest.mark.django_db
def test_login_works(otis):
    otis.get_20x("account_login")


@pytest.mark.parametrize(
    "path",
    (
        "/wiki",
        "/wiki/",
        "/wiki/Main_Page",
        "/wiki/some/deeply/nested/page/",
        "/wiki/page?query=1",
    ),
)
def test_wiki_redirects_to_catalog(client: Client, path: str):
    response = client.get(path)
    assert response.status_code == 301
    assert response["Location"] == "https://catalog.evanchen.cc/"


@pytest.mark.parametrize("path", ("/wikipedia/", "/wikis/"))
def test_wiki_redirect_does_not_overreach(client: Client, path: str):
    assert client.get(path).status_code == 404


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.addFilter(fix_response_location)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _log_server_error(rf: RequestFactory, path: str) -> logging.LogRecord:
    request = rf.get(path)
    try:
        request.resolver_match = resolve(path)
    except Resolver404:
        pass
    logger = logging.getLogger("otisweb.tests.response_location")
    logger.propagate = False
    handler = _Capture()
    logger.addHandler(handler)
    try:
        log_response(
            "Internal Server Error: %s",
            path,
            response=HttpResponse(status=500),
            request=request,
            logger=logger,
        )
    finally:
        logger.removeHandler(handler)
    (record,) = handler.records
    return record


def test_response_location_unfiltered(rf: RequestFactory):
    record = _log_server_error(rf, "/nonexistent/")
    assert record.module == "log"
    assert record.pathname.endswith(os.path.join("django", "utils", "log.py"))


@pytest.mark.parametrize(
    "path,expected_module",
    (
        ("/arch/", "arch.views.ProblemCreate"),
        ("/dash/portal/1/", "dashboard.views.portal"),
    ),
)
def test_response_location_view(rf: RequestFactory, path: str, expected_module: str):
    record = _log_server_error(rf, path)
    assert record.module == expected_module
    assert record.filename == "views.py"
    assert record.pathname.endswith(
        os.path.join(expected_module.split(".")[0], "views.py")
    )
    assert record.lineno > 0
