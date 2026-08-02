import pytest
from django.test import Client

from core.factories import UserFactory


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
    assert response.status_code == 302
    assert response["Location"] == "https://catalog.evanchen.cc/"


@pytest.mark.parametrize("path", ("/wikipedia/", "/wikis/"))
def test_wiki_redirect_does_not_overreach(client: Client, path: str):
    assert client.get(path).status_code == 404
