import re

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import Group, User
from django.contrib.messages import constants as message_levels
from django.urls import reverse

from core.factories import SemesterFactory, UserFactory
from roster.factories import StudentFactory
from roster.models import Student


def lookup_user(username: str, first: str, last: str, **kwargs: bool) -> User:
    """UserFactory with every field the lookup view searches pinned.

    The view matches username, email, first name and last name, so faker's
    random names would otherwise collide with a short query like "BO" and
    make the result counts in the lookup tests flaky.
    """
    return UserFactory.create(
        username=username,
        email=f"{username}@example.com",
        first_name=first,
        last_name=last,
        **kwargs,
    )


def login_lookup_admin(otis) -> User:
    return otis.login(
        lookup_user("admin", "Ada", "Min", is_superuser=True, is_staff=True)
    )


@pytest.mark.django_db
def test_user_lookup_requires_superuser(otis) -> None:
    otis.get_30x("user-lookup")
    otis.login(lookup_user("regular", "Reg", "Ular"))
    otis.get_40x("user-lookup")
    otis.login(lookup_user("staffer", "Stef", "Ann", is_staff=True))
    otis.get_40x("user-lookup")


@pytest.mark.django_db
def test_user_lookup_get_shows_no_results(otis) -> None:
    login_lookup_admin(otis)
    resp = otis.get_20x("user-lookup")
    assert resp.context["results"] is None


@pytest.mark.django_db
def test_user_lookup_by_email(otis) -> None:
    alice = lookup_user("alice", "Alice", "Adams")
    StudentFactory.create(user=alice, semester=SemesterFactory.create(end_year=2025))
    alice_new = StudentFactory.create(
        user=alice, semester=SemesterFactory.create(end_year=2026)
    )
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": "alice@example.com"})
    (result,) = resp.context["results"]
    assert result["user"] == alice
    assert alice_new in result["students"]
    otis.assert_has(resp, reverse("user-info", args=(alice.pk,)))


@pytest.mark.django_db
def test_user_lookup_by_username_substring(otis) -> None:
    lookup_user("alice", "Alice", "Adams")
    bob = lookup_user("bob", "Bob", "Byrne")
    bob_student = StudentFactory.create(user=bob)
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": "BO"})
    (result,) = resp.context["results"]
    assert result["user"] == bob
    assert bob_student in result["students"]


@pytest.mark.django_db
def test_user_lookup_by_real_name(otis) -> None:
    alice = lookup_user("alice", "Alice", "Adams")
    lookup_user("bob", "Bob", "Byrne")
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": "Alice"})
    assert [r["user"] for r in resp.context["results"]] == [alice]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("provider", "extra_data", "query", "label"),
    [
        ("discord", {"username": "bobdiscord"}, "bobdiscord", "Discord (bobdiscord)"),
        ("github", {"login": "bobhub"}, "bobhub", "GitHub (bobhub)"),
    ],
)
def test_user_lookup_by_social_account(
    otis, provider: str, extra_data: dict[str, str], query: str, label: str
) -> None:
    bob = lookup_user("bob", "Bob", "Byrne")
    SocialAccount.objects.create(
        user=bob, provider=provider, uid="12345", extra_data=extra_data
    )
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": query})
    (result,) = resp.context["results"]
    assert result["user"] == bob
    assert label in result["socials"]


@pytest.mark.django_db
def test_user_lookup_finds_user_without_students(otis) -> None:
    carl = lookup_user("carl", "Carl", "Chen")
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": "carl@example.com"})
    (result,) = resp.context["results"]
    assert result["user"] == carl
    assert result["students"] == []


@pytest.mark.django_db
def test_user_lookup_no_matches(otis) -> None:
    login_lookup_admin(otis)
    resp = otis.post_20x("user-lookup", data={"query": "nonexistent-query-zzz"})
    assert resp.context["results"] == []
    otis.assert_testid(resp, "user-lookup-no-matches")


@pytest.mark.django_db
def test_user_lookup_flags_inactive_accounts(otis) -> None:
    alice = lookup_user("alice", "Alice", "Adams")
    login_lookup_admin(otis)

    resp = otis.post_20x("user-lookup", data={"query": "alice"})
    otis.assert_no_testid(resp, "user-inactive-badge")

    alice.is_active = False
    alice.save()
    resp = otis.post_20x("user-lookup", data={"query": "alice"})
    otis.assert_testid(resp, "user-inactive-badge")


def merge_data(impostor: User, crewmate: User) -> dict[str, int]:
    return {"impostor": impostor.pk, "crewmate": crewmate.pk}


def login_admin(otis) -> User:
    return otis.login(UserFactory.create(is_superuser=True, is_staff=True))


@pytest.mark.django_db
def test_user_merge_requires_superuser(otis) -> None:
    dupe, real = UserFactory.create_batch(2)
    otis.post_30x("user-merge", data=merge_data(dupe, real))
    otis.login(UserFactory.create(is_staff=True))
    otis.post_40x("user-merge", data=merge_data(dupe, real))
    dupe.refresh_from_db()
    assert dupe.is_active


@pytest.mark.django_db
def test_user_merge_get_redirects_to_lookup(otis) -> None:
    login_admin(otis)
    otis.assert_redirects(otis.get("user-merge"), reverse("user-lookup"))


@pytest.mark.django_db
def test_user_merge_rejects_same_account(otis) -> None:
    dupe = UserFactory.create()
    login_admin(otis)
    resp = otis.post_20x("user-merge", data=merge_data(dupe, dupe))
    assert not resp.context["merge_form"].is_valid()
    assert "distinct" in str(resp.context["merge_form"].errors)
    assert resp.context["merge_open"]


@pytest.mark.django_db
def test_user_merge_rejects_staff_impostor(otis) -> None:
    real = UserFactory.create()
    admin = login_admin(otis)
    resp = otis.post_20x("user-merge", data=merge_data(admin, real))
    assert "Merge this one by hand." in str(resp.context["merge_form"].errors)


@pytest.mark.django_db
def test_user_merge_rejects_students_in_same_semester(otis) -> None:
    semester = SemesterFactory.create()
    dupe, real = UserFactory.create_batch(2)
    StudentFactory.create(user=dupe, semester=semester)
    StudentFactory.create(user=real, semester=semester)
    login_admin(otis)

    resp = otis.post_20x("user-merge", data=merge_data(dupe, real))
    assert "Delete the redundant student(s) first." in str(
        resp.context["merge_form"].errors
    )
    assert Student.objects.filter(user=dupe).count() == 1


@pytest.mark.django_db
def test_user_merge_rejects_nonexistent_crewmate(otis) -> None:
    real = UserFactory.create()
    login_admin(otis)
    resp = otis.post_20x(
        "user-merge",
        data={"impostor": real.pk, "crewmate": 999999, "confirmed": True},
    )
    assert not resp.context["merge_form"].is_valid()
    assert resp.context["merge_open"]
    real.refresh_from_db()
    assert real.is_active is True


@pytest.fixture
def merge_pair() -> tuple[User, User]:
    """An impostor with an old student, a Discord account and two groups,
    one of which the crewmate is already in."""
    dupe = UserFactory.create(username="alice2")
    real = UserFactory.create(username="alice")
    StudentFactory.create(user=dupe, semester=SemesterFactory.create(end_year=2025))
    StudentFactory.create(user=real, semester=SemesterFactory.create(end_year=2026))
    SocialAccount.objects.create(
        user=dupe,
        provider="discord",
        uid="12345",
        extra_data={"username": "alicediscord"},
    )
    Group.objects.create(name="Verified").user_set.add(dupe)  # type: ignore
    Group.objects.create(name="Active").user_set.add(dupe, real)  # type: ignore
    return dupe, real


@pytest.mark.django_db
def test_user_merge_preview_changes_nothing(otis, merge_pair) -> None:
    dupe, real = merge_pair
    dupe_student = Student.objects.get(user=dupe)
    login_admin(otis)

    resp = otis.post_20x("user-merge", data=merge_data(dupe, real))
    otis.assert_testid(resp, "merge-preview-note")
    assert resp.context["impostor"]["user"] == dupe
    assert resp.context["crewmate"]["user"] == real
    assert resp.context["impostor"]["students"] == [dupe_student]
    assert "Discord (alicediscord)" in resp.context["impostor"]["socials"]
    assert sorted(g.name for g in resp.context["impostor"]["groups"]) == [
        "Active",
        "Verified",
    ]

    dupe.refresh_from_db()
    assert dupe.is_active is True
    assert dupe.groups.count() == 2
    assert real.groups.count() == 1
    assert Student.objects.filter(user=dupe).count() == 1


@pytest.mark.django_db
def test_user_merge_confirmed_hands_everything_over(otis, merge_pair) -> None:
    dupe, real = merge_pair
    login_admin(otis)

    preview = otis.post_20x("user-merge", data=merge_data(dupe, real))
    hidden_inputs = {
        name.decode(): value.decode()
        for name, value in re.findall(rb'name="(\w+)" value="([^"]*)"', preview.content)
    }
    assert hidden_inputs["impostor"] == str(dupe.pk)
    assert hidden_inputs["crewmate"] == str(real.pk)

    resp = otis.post_30x("user-merge", data=hidden_inputs)
    otis.assert_redirects(resp, reverse("user-lookup"))
    dupe.refresh_from_db()
    assert dupe.is_active is False
    assert dupe.groups.count() == 0
    assert sorted(g.name for g in real.groups.all()) == ["Active", "Verified"]
    assert Student.objects.filter(user=real).count() == 2
    assert SocialAccount.objects.get().user == real


def profile_data(user: User, **overrides: str) -> dict[str, str]:
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        **overrides,
    }


@pytest.mark.django_db
def test_update_profile_page_loads(otis) -> None:
    otis.login(UserFactory.create())
    otis.get_20x("update-profile")


@pytest.mark.django_db
def test_update_profile_rejects_invalid_email(otis) -> None:
    alice = UserFactory.create(first_name="Alice")
    otis.login(alice)

    resp = otis.post_20x(
        "update-profile",
        data=profile_data(alice, first_name="Alicia", email="invalid_Email!!"),
    )
    assert "email" in resp.context["form"].errors
    alice.refresh_from_db()
    assert alice.first_name == "Alice"


@pytest.mark.django_db
def test_update_profile_changes_name(otis) -> None:
    alice = UserFactory.create()
    email = alice.email
    otis.login(alice)

    resp = otis.post_20x(
        "update-profile",
        data=profile_data(alice, first_name="Alicia", last_name="Aardvark"),
    )
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    alice.refresh_from_db()
    assert alice.first_name == "Alicia"
    assert alice.last_name == "Aardvark"
    assert alice.email == email


@pytest.mark.django_db
def test_update_profile_changes_email(otis) -> None:
    alice = UserFactory.create()
    first_name = alice.first_name
    new_email = f"1{alice.email}"
    otis.login(alice)

    otis.post_20x("update-profile", data=profile_data(alice, email=new_email))
    alice.refresh_from_db()
    assert alice.email == new_email
    assert alice.first_name == first_name


@pytest.mark.django_db
def test_student_ids_requires_login(otis) -> None:
    otis.get_30x("student-ids")


@pytest.mark.django_db
def test_student_ids_lists_only_own_students(otis) -> None:
    alice = UserFactory.create()
    semester_old = SemesterFactory.create(end_year=2024)
    semester_new = SemesterFactory.create(end_year=2025)
    student_old = StudentFactory.create(user=alice, semester=semester_old)
    student_new = StudentFactory.create(user=alice, semester=semester_new)
    StudentFactory.create(semester=semester_new)

    otis.login(alice)
    resp = otis.get_20x("student-ids")
    assert set(resp.context["students"]) == {student_old, student_new}
