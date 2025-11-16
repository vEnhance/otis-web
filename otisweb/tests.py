import pytest

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
