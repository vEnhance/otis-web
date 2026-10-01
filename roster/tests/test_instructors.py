import pytest
from django.contrib.auth.models import Group

from core.factories import UserFactory
from roster.factories import AssistantFactory, StudentFactory
from roster.models import Assistant
from roster.utils import get_visible_students


@pytest.fixture
def instructors() -> list[Assistant]:
    """Three instructors with 1, 2, 3 students of their own, one student
    shared by the first two, and one student with no instructor at all."""
    assistants = [
        AssistantFactory.create(
            user__first_name=f"F{i}",
            user__last_name=f"L{i}",
            user__email=f"user{i}@evanchen.cc",
        )
        for i in range(1, 4)
    ]
    for i, asst in enumerate(assistants, start=1):
        StudentFactory.create_batch(i, user__first_name="GoodKid", assistants=[asst])
    StudentFactory.create(user__first_name="GoodKid", assistants=assistants[:2])
    StudentFactory.create(user__first_name="BadKid")
    return assistants


@pytest.mark.django_db
def test_instructor_list_counts_students(otis, instructors) -> None:
    otis.login(UserFactory.create(is_staff=True))
    resp = otis.get_20x("instructors")
    assert len(resp.context["students"]) == 1 + 2 + 3 + 1
    assert all(s.user.first_name == "GoodKid" for s in resp.context["students"])
    assert {a.pk: len(a.active_students) for a in resp.context["instructors"]} == {
        instructors[0].pk: 2,
        instructors[1].pk: 3,
        instructors[2].pk: 3,
    }


@pytest.mark.django_db
def test_instructor_list_mailing_addresses(otis, instructors) -> None:
    otis.login(UserFactory.create(is_staff=True))
    # a mailing list, so the rendered address text is the product
    resp = otis.get_20x("instructors")
    for i in range(1, 4):
        otis.assert_has(resp, f'"F{i} L{i}"')
        otis.assert_has(resp, f"user{i}@evanchen.cc")
    otis.assert_has(resp, r"&lt;user3@evanchen.cc&gt;")
    otis.assert_not_has(resp, "BadKid")


@pytest.mark.django_db
def test_instructor_list_sync_warning_is_admin_only(otis, instructors) -> None:
    otis.login(UserFactory.create(is_staff=True))
    resp = otis.get_20x("instructors")
    assert resp.context["needs_sync"]
    otis.assert_no_testid(resp, "staff-group-out-of-sync")

    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.assert_testid(otis.get_20x("instructors"), "staff-group-out-of-sync")


@pytest.mark.django_db
def test_instructor_list_sync_fills_staff_group(otis, instructors) -> None:
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    resp = otis.post_ok("instructors")
    assert not resp.context["needs_sync"]
    assert set(Group.objects.get(name="Active Staff").user_set.all()) == {  # type: ignore
        a.user for a in instructors
    }
    assert not otis.get_ok("instructors").context["needs_sync"]


@pytest.mark.django_db
def test_instructor_list_sync_requires_superuser(otis, instructors) -> None:
    otis.login(UserFactory.create(is_staff=True))
    otis.post_40x("instructors")
    assert not Group.objects.filter(name="Active Staff", user__isnull=False).exists()


@pytest.mark.django_db
def test_co_instructors_both_see_student(otis) -> None:
    first, second = AssistantFactory.create_batch(2)
    alice = StudentFactory.create(assistants=[first, second])
    for assistant in (first, second):
        assert list(get_visible_students(assistant.user)) == [alice]
        otis.login(assistant.user)
        otis.get_20x("portal", alice.pk, follow=True)


@pytest.mark.django_db
def test_student_sees_only_self(otis) -> None:
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    StudentFactory.create()
    assert list(get_visible_students(alice.user)) == [alice]


@pytest.mark.django_db
def test_other_instructor_cannot_see_student(otis) -> None:
    stranger = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    assert not get_visible_students(stranger.user).exists()
    otis.login(stranger.user)
    otis.get_denied("portal", alice.pk)


@pytest.mark.django_db
def test_link_assistant_requires_staff(otis) -> None:
    otis.get_30x("link-assistant")
    otis.login(UserFactory.create(is_staff=False))
    otis.get_40x("link-assistant")


@pytest.mark.django_db
def test_link_assistant_offers_only_unpaired_students(otis) -> None:
    assistant = AssistantFactory.create()
    StudentFactory.create_batch(2)
    StudentFactory.create(assistants=[assistant])
    StudentFactory.create(assistants=[AssistantFactory.create()])
    otis.login(assistant.user)
    resp = otis.get_ok("link-assistant")
    assert len(resp.context["form"].fields["student"].queryset) == 2


@pytest.mark.django_db
def test_link_assistant(otis) -> None:
    assistant = AssistantFactory.create()
    alice = StudentFactory.create()
    otis.login(assistant.user)
    otis.post_ok("link-assistant", data={"student": alice.pk})
    assert list(alice.assistants.all()) == [assistant]
