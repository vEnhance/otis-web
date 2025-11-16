"""
Pytest fixtures for OTIS-WEB testing.

Provides the same conveniences as EvanTestCase but in pytest-style fixtures.
"""

import json
import logging
import pprint
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.test import RequestFactory
from django.test.client import Client
from django.urls.base import resolve, reverse

if TYPE_CHECKING:  # pragma: no cover
    from django.test.client import _MonkeyPatchedWSGIResponse  # type: ignore  # NOQA

    MonkeyResponseType = _MonkeyPatchedWSGIResponse  # type: ignore
else:
    MonkeyResponseType = Any


class OTISClient:
    """
    Enhanced Django test client with convenient assertion methods.

    Provides the same functionality as EvanTestCase but as a standalone client.
    """

    def __init__(self, client: Client):
        self.client = client

    def debug_short(self, response: MonkeyResponseType) -> str:
        d: dict[str, Any] = {}
        for key in ("headers", "json", "redirect_chain", "request", "wsgi_request"):
            d[key] = getattr(response, key, None)
        return "\n" + pprint.pformat(d, compact=False, depth=3) + "\n"

    def debug_dump(self, response: MonkeyResponseType) -> None:
        timestamp = datetime.now().strftime("%d_%b_%Y_%H%M%S")
        html_path = Path(f"/tmp/{settings.WSGI_APPLICATION}.tests/{timestamp}.html")
        txt_path = Path(f"/tmp/{settings.WSGI_APPLICATION}.tests/{timestamp}.txt")

        try:
            html_path.parent.mkdir(exist_ok=True)
        except PermissionError:
            pass
        else:
            if len(response.content) > 0:
                logging.info(f"Wrote to {html_path}")
                html_path.write_bytes(response.content)
                txt_path.write_text(pprint.pformat(response.__dict__, depth=3))

    # Response assertions
    def assert_20x(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert 200 <= response.status_code < 300, self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_30x(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert 300 <= response.status_code < 400, self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_ok(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert response.status_code < 400, self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_40x(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert 400 <= response.status_code < 500, self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_denied(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert response.status_code in (400, 403), self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_not_found(self, response: MonkeyResponseType) -> MonkeyResponseType:
        try:
            assert response.status_code == 404, self.debug_short(response)
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    # Aliases for backward compatibility
    assert_response_20x = assert_20x
    assert_response_30x = assert_30x
    assert_response_40x = assert_40x
    assert_response_denied = assert_denied
    assert_response_not_found = assert_not_found
    assert_response_ok = assert_ok

    def assert_has(
        self, response: MonkeyResponseType, text: Union[bytes, int, str, Any], count: int = 0
    ) -> MonkeyResponseType:
        if isinstance(text, int):
            text = str(text)
        if not isinstance(text, (bytes, str)):
            text = str(text)
        if isinstance(text, str):
            text = text.encode()
        try:
            if count > 0:
                actual_count = response.content.count(text)
                assert actual_count == count, (
                    f"Found {actual_count} occurrences of {text!r}, expected {count}\n{self.debug_short(response)}"
                )
            else:
                assert text in response.content, (
                    f"Could not find {text!r} in response\n{self.debug_short(response)}"
                )
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_not_has(
        self, response: MonkeyResponseType, text: Union[bytes, str]
    ) -> MonkeyResponseType:
        if isinstance(text, str):
            text = text.encode()
        try:
            assert text not in response.content, (
                f"Found {text!r} in response\n{self.debug_short(response)}"
            )
        except AssertionError:
            self.debug_dump(response)
            raise
        return response

    def assert_message(
        self, response: MonkeyResponseType, text: Union[bytes, int, str]
    ) -> MonkeyResponseType:
        messages = [m.message for m in response.context["messages"] or []]
        assert text in messages, f"Message {text!r} not found in {messages}"
        return response

    def assert_no_messages(self, response: MonkeyResponseType) -> MonkeyResponseType:
        assert len(response.context["messages"]) == 0
        return response

    def assert_redirects(
        self, response: MonkeyResponseType, target: str
    ) -> MonkeyResponseType:
        # Handle followed redirects (status 200 with redirect_chain)
        if hasattr(response, "redirect_chain") and response.redirect_chain:
            # Response followed redirects, check final URL
            final_url = response.redirect_chain[-1][0]
            assert final_url == target or target in final_url, (
                f"Expected redirect to {target}, got {final_url}\n{self.debug_short(response)}"
            )
        else:
            # Response didn't follow, check redirect status
            assert response.status_code in (301, 302, 303, 307, 308), (
                f"Expected redirect, got {response.status_code}\n{self.debug_short(response)}"
            )
            redirect_url = response.url if hasattr(response, "url") else response.headers.get("Location", "")
            assert redirect_url == target or target in redirect_url, (
                f"Expected redirect to {target}, got {redirect_url}\n{self.debug_short(response)}"
            )
        return response

    # HTTP methods with URL name support
    def get(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        if (json_data := kwargs.pop("json", None)) is not None:
            kwargs["content_type"] = "application/json"
            kwargs["data"] = json.dumps(json_data)
        return self.client.get(reverse(name, args=args), **kwargs)

    def post(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        if (json_data := kwargs.pop("json", None)) is not None:
            kwargs["content_type"] = "application/json"
            kwargs["data"] = json.dumps(json_data)
        return self.client.post(reverse(name, args=args), **kwargs)

    def url(self, name: str, *args: Any) -> str:
        return reverse(name, args=args)

    # Convenience methods combining HTTP + assertion
    def get_ok(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_ok(self.get(name, *args, **kwargs))

    def get_20x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_20x(self.get(name, *args, **kwargs))

    def get_30x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_30x(self.get(name, *args, **kwargs))

    def get_40x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_40x(self.get(name, *args, **kwargs))

    def get_denied(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_denied(self.get(name, *args, **kwargs))

    def get_not_found(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_not_found(self.get(name, *args, **kwargs))

    def get_redirects(
        self, target: str, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        return self.assert_redirects(self.get(name, *args, **kwargs), target)

    def post_ok(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_ok(self.post(name, *args, **kwargs))

    def post_20x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_20x(self.post(name, *args, **kwargs))

    def post_30x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_30x(self.post(name, *args, **kwargs))

    def post_40x(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_40x(self.post(name, *args, **kwargs))

    def post_denied(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_denied(self.post(name, *args, **kwargs))

    def post_not_found(self, name: str, *args: Any, **kwargs: Any) -> MonkeyResponseType:
        return self.assert_not_found(self.post(name, *args, **kwargs))

    def post_redirects(
        self, target: str, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        return self.assert_redirects(self.post(name, *args, **kwargs), target)

    # Login helpers
    def login(self, obj: Union[str, models.Model]) -> User:
        if isinstance(obj, str):
            user = User.objects.get(username=obj)
            self.client.force_login(user)
            return user
        elif isinstance(obj, User):
            self.client.force_login(obj)
            return obj
        elif hasattr(obj, "user"):
            user = getattr(obj, "user")
            self.client.force_login(user)
            return user
        else:
            raise TypeError(f"Cannot login with {type(obj)}")

    # Redirect assertions
    def get_login_redirect(
        self, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        expected = "/accounts/login/?next=" + reverse(name, args=args)
        return self.assert_redirects(self.get(name, *args, **kwargs), expected)

    def post_login_redirect(
        self, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        expected = "/accounts/login/?next=" + reverse(name, args=args)
        return self.assert_redirects(self.post(name, *args, **kwargs), expected)

    def get_staff_redirect(
        self, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        expected = "/admin/login/?next=" + reverse(name, args=args)
        return self.assert_redirects(self.get(name, *args, **kwargs), expected)

    def post_staff_redirect(
        self, name: str, *args: Any, **kwargs: Any
    ) -> MonkeyResponseType:
        expected = "/admin/login/?next=" + reverse(name, args=args)
        return self.assert_redirects(self.post(name, *args, **kwargs), expected)

    # View setup helper
    def setup_view_get(self, view_class: type, name: str, *args: Any, **kwargs: Any):
        url = reverse(name, args=args)
        request = RequestFactory().get(url, **kwargs)
        resolver_match = resolve(url)
        view = view_class()
        view.setup(request, *resolver_match.args, **resolver_match.kwargs)  # type: ignore
        return view


@pytest.fixture
def otis(client: Client) -> OTISClient:
    """
    Pytest fixture providing an enhanced test client with OTIS conveniences.

    Usage:
        def test_something(otis):
            otis.login(alice)
            resp = otis.get_20x("view-name", arg1, arg2)
            otis.assert_has(resp, "expected text")
    """
    return OTISClient(client)
