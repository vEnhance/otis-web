import pytest
from django.urls import reverse

from core.factories import GroupFactory, UserFactory


@pytest.mark.django_db
def test_userinfo_access_control(otis):
    target_user = UserFactory.create()

    # Anonymous -> redirect to login
    otis.get_30x("user-info", target_user.pk)

    # Regular user -> denied
    otis.login(UserFactory.create())
    otis.get_40x("user-info", target_user.pk)

    # Staff only (not superuser) -> denied
    otis.login(UserFactory.create(is_staff=True))
    otis.get_40x("user-info", target_user.pk)

    # Superuser -> success
    otis.login(UserFactory.create(is_superuser=True, is_staff=True))
    otis.get_20x("user-info", target_user.pk)


@pytest.mark.django_db
def test_userinfo_displays_info(otis):
    target_user = UserFactory.create(
        username="testuser",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        is_staff=True,
    )
    target_user.groups.add(GroupFactory.create(name="Testers"))
    admin = UserFactory.create(is_superuser=True, is_staff=True)
    otis.login(admin)
    resp = otis.get_20x("user-info", target_user.pk)
    assert resp.context["target_user"] == target_user
    assert [g.name for g in resp.context["groups"]] == ["Testers"]
    assert target_user.last_login is None
    otis.assert_has(resp, reverse("admin:auth_user_change", args=(target_user.pk,)))
    otis.assert_no_testid(resp, "user-inactive-warning")


@pytest.mark.django_db
def test_userinfo_shows_hijack_button(otis):
    target_user = UserFactory.create()
    otis.login(UserFactory.create(is_superuser=True, is_staff=True))
    resp = otis.get_20x("user-info", target_user.pk)
    otis.assert_testid(resp, "hijack-button")
    otis.assert_has(resp, reverse("hijack:acquire"))


@pytest.mark.django_db
def test_userinfo_warns_on_inactive(otis):
    target_user = UserFactory.create(is_active=False)
    otis.login(UserFactory.create(is_superuser=True, is_staff=True))
    resp = otis.get_20x("user-info", target_user.pk)
    otis.assert_testid(resp, "user-inactive-warning")


@pytest.mark.django_db
def test_generate_reset_link_access_control(otis):
    target_user = UserFactory.create()

    # Anonymous -> redirect
    otis.post_login_redirect("generate-reset-link", target_user.pk)

    # Regular user -> denied
    otis.login(UserFactory.create())
    otis.post_denied("generate-reset-link", target_user.pk)

    # Staff only -> denied
    otis.login(UserFactory.create(is_staff=True))
    otis.post_denied("generate-reset-link", target_user.pk)


@pytest.mark.django_db
def test_generate_reset_link(otis):
    target_user = UserFactory.create()
    admin = UserFactory.create(is_superuser=True, is_staff=True)
    otis.login(admin)

    # POST to generate link
    resp = otis.post("generate-reset-link", target_user.pk)
    otis.assert_30x(resp)

    # Follow redirect and check link is displayed
    resp = otis.get_20x("user-info", target_user.pk)
    assert "/core/reset/" in resp.context["reset_link"]
