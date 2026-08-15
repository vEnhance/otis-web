import logging
import os

import pytest
from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages.storage.base import Message
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.models import Site
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.urls import Resolver404, resolve, reverse
from django.utils.log import log_response

from core.factories import UserFactory
from otisweb.adapters import AUTH_PROCESS_LOGIN_EXISTING
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


@pytest.fixture
def google_app() -> SocialApp:
    app = SocialApp.objects.create(
        provider="google",
        name="Google",
        client_id="fake-client-id",
        secret="fake-secret",
    )
    app.sites.add(Site.objects.get_current())
    return app


def _social_request() -> HttpRequest:
    """Build a request with the session and message plumbing allauth needs."""
    request = RequestFactory().get(reverse("account_login"))
    request.user = AnonymousUser()
    SessionMiddleware(lambda _: HttpResponse()).process_request(request)
    request.session.save()
    MessageMiddleware(lambda _: HttpResponse()).process_request(request)
    return request


def _attempt_social_login(
    request: HttpRequest,
    uid: str,
    email: str,
    process: str = AUTH_PROCESS_LOGIN_EXISTING,
    email_verified: bool = True,
) -> HttpResponse:
    """Run a social login callback as if the provider had just answered."""
    provider = get_socialaccount_adapter().get_provider(request, "google")
    sociallogin = provider.sociallogin_from_response(
        request,
        {
            "sub": uid,
            "email": email,
            "email_verified": email_verified,
        },
    )
    sociallogin.state = {"process": process}
    with request_context(request):
        return complete_social_login(request, sociallogin)


def _get_messages(request: HttpRequest) -> list[Message]:
    from django.contrib.messages import get_messages

    return list(get_messages(request))


@pytest.mark.django_db
def test_login_page_offers_login_only_social_option(otis, google_app: SocialApp):
    response = otis.get_20x("account_login")
    # The first accordion must not create accounts; the last one must.
    otis.assert_has(
        response, f'"/accounts/google/login/?process={AUTH_PROCESS_LOGIN_EXISTING}"'
    )
    otis.assert_has(response, '"/accounts/google/login/?process=login"')


@pytest.mark.django_db
def test_social_login_interstitial_warns_about_login_only(otis, google_app: SocialApp):
    warning = b"you'll get an error rather than a new account"
    response = otis.assert_20x(
        otis.client.get(
            f"/accounts/google/login/?process={AUTH_PROCESS_LOGIN_EXISTING}"
        )
    )
    otis.assert_has(response, warning)
    otis.assert_not_has(
        otis.assert_20x(otis.client.get("/accounts/google/login/?process=login")),
        warning,
    )


@pytest.mark.django_db
def test_social_login_existing_refuses_to_create_account(google_app: SocialApp):
    request = _social_request()
    response = _attempt_social_login(request, uid="12345", email="nobody@evanchen.cc")
    assert response.status_code == 302
    assert response["Location"] == reverse("account_login")  # type: ignore
    assert not User.objects.exists()
    assert not SocialAccount.objects.exists()
    (message,) = _get_messages(request)
    assert "no new account was created" in message.message


@pytest.mark.django_db
def test_social_login_existing_works_for_connected_account(google_app: SocialApp):
    alice = UserFactory.create(username="alice", email="alice@evanchen.cc")
    SocialAccount.objects.create(user=alice, provider="google", uid="12345")
    request = _social_request()
    response = _attempt_social_login(request, uid="12345", email="alice@evanchen.cc")
    assert response.status_code == 302
    assert response["Location"] != reverse("account_login")  # type: ignore
    assert request.user == alice
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_social_login_existing_names_the_provider_actually_used(google_app: SocialApp):
    alice = UserFactory.create(username="alice", email="alice@evanchen.cc")
    SocialAccount.objects.create(user=alice, provider="google", uid="11111")
    request = _social_request()
    # Same human, same email, but a second Google account they forgot about.
    _attempt_social_login(request, uid="22222", email="alice@evanchen.cc")
    (message,) = _get_messages(request)
    assert "signs in with: Google" in message.message
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_social_login_existing_mentions_password_only_accounts(google_app: SocialApp):
    alice = UserFactory.create(username="alice", email="alice@evanchen.cc")
    EmailAddress.objects.create(user=alice, email="alice@evanchen.cc", verified=True)
    request = _social_request()
    _attempt_social_login(request, uid="12345", email="alice@evanchen.cc")
    (message,) = _get_messages(request)
    assert "username and password" in message.message


@pytest.mark.django_db
def test_social_login_existing_keeps_quiet_about_unverified_emails(
    google_app: SocialApp,
):
    UserFactory.create(username="alice", email="alice@evanchen.cc")
    request = _social_request()
    _attempt_social_login(
        request, uid="12345", email="alice@evanchen.cc", email_verified=False
    )
    (message,) = _get_messages(request)
    assert "alice" not in message.message
    assert "signs in with" not in message.message


@pytest.mark.django_db
def test_social_signup_still_creates_new_accounts(google_app: SocialApp):
    request = _social_request()
    response = _attempt_social_login(
        request, uid="12345", email="newbie@evanchen.cc", process="login"
    )
    assert response.status_code == 302
    assert response["Location"] != reverse("account_login")  # type: ignore
    assert User.objects.filter(email="newbie@evanchen.cc").exists()
    assert SocialAccount.objects.filter(provider="google", uid="12345").exists()


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
