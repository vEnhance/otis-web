import pytest
from django.urls import reverse
from freezegun import freeze_time

from core.factories import SemesterFactory, UserFactory
from dashboard.factories import PSetFactory, SemesterDownloadFileFactory
from roster.factories import (
    AssistantFactory,
    RegistrationContainerFactory,
    StudentFactory,
)
from roster.models import Student


@pytest.mark.django_db
def test_index_without_students(otis) -> None:
    otis.login(UserFactory.create())
    resp = otis.get_20x("index")
    assert resp.context["rows"] == []
    otis.assert_no_testid(resp, "stulist-empty-staff")


@pytest.mark.django_db
def test_index_without_students_as_staff(otis) -> None:
    otis.login(UserFactory.create(is_staff=True))
    otis.assert_testid(otis.get_20x("index"), "stulist-empty-staff")


@pytest.mark.django_db
def test_index_points_to_open_registration(otis) -> None:
    RegistrationContainerFactory.create()
    otis.login(UserFactory.create())
    resp = otis.get_20x("index")
    assert resp.context["exists_registration"] is True
    otis.assert_testid(resp, "stulist-empty-register")


@pytest.mark.django_db
def test_index_redirects_single_student_to_portal(otis) -> None:
    alice = StudentFactory.create()
    otis.login(alice)
    otis.get_redirects(reverse("portal", args=(alice.pk,)), "index", follow=True)


@pytest.mark.django_db
def test_index_lists_instructors_students(otis) -> None:
    assistant = AssistantFactory.create()
    students = set(StudentFactory.create_batch(2, assistants=[assistant]))
    StudentFactory.create()
    otis.login(assistant)
    resp = otis.get_20x("index")
    assert {row["student"] for row in resp.context["rows"]} == students


@pytest.fixture
def past_alice() -> Student:
    """Alice from an archived year, with an accepted pset worth level 38."""
    past_alice = StudentFactory.create(semester__active=False)
    PSetFactory.create(student=past_alice, clubs=0, hours=1501, status="A")
    return past_alice


@pytest.mark.django_db
def test_past_lists_every_year(otis, past_alice) -> None:
    alice = StudentFactory.create(user=past_alice.user)
    otis.login(alice)
    resp = otis.get_20x("past")
    assert resp.context["past"] is True
    assert resp.context["stulist_show_semester"] is True
    assert {row["student"] for row in resp.context["rows"]} == {alice, past_alice}


@pytest.mark.django_db
def test_past_for_one_semester(otis, past_alice) -> None:
    otis.login(StudentFactory.create(user=past_alice.user))
    resp = otis.get_20x("past", past_alice.semester.pk)
    assert resp.context["semester"] == past_alice.semester
    assert resp.context["stulist_show_semester"] is False
    (row,) = resp.context["rows"]
    assert row["student"] == past_alice
    assert row["level"] == 38


@pytest.mark.django_db
def test_past_for_one_semester_as_instructor(otis, past_alice) -> None:
    assistant = AssistantFactory.create()
    past_alice.assistants.add(assistant)
    bob = StudentFactory.create(assistants=[assistant], semester=past_alice.semester)
    otis.login(assistant)
    resp = otis.get_20x("past", past_alice.semester.pk)
    rows = {row["student"]: row for row in resp.context["rows"]}
    assert set(rows) == {past_alice, bob}
    assert rows[past_alice]["level"] == 38


@pytest.mark.django_db
@pytest.mark.parametrize("is_superuser", [False, True])
def test_semester_list(otis, is_superuser: bool) -> None:
    past_semester = SemesterFactory.create(active=False)
    otis.login(StudentFactory.create(user__is_superuser=is_superuser))
    resp = otis.get_20x("semester-list")
    assert past_semester in resp.context["object_list"]
    if is_superuser:
        otis.assert_testid(resp, "semester-student-count")
    else:
        otis.assert_no_testid(resp, "semester-student-count")


@pytest.mark.django_db
def test_idle_warn(otis) -> None:
    user = UserFactory.create(is_staff=True, is_superuser=True)
    alice = StudentFactory.create(assistants=[AssistantFactory.create(user=user)])
    with freeze_time("2021-07-01", tz_offset=0):
        PSetFactory.create(student=alice, clubs=0, hours=1501, status="A")
    otis.login(user)

    with freeze_time("2021-07-29", tz_offset=0):
        resp = otis.get_20x("idlewarn")
    (row,) = resp.context["rows"]
    assert row["student"] == alice
    assert row["level"] == 38
    assert row["days_since_last_pset"] == pytest.approx(28.0)


@pytest.mark.django_db
def test_download_list(otis) -> None:
    alice = StudentFactory.create()
    download = SemesterDownloadFileFactory.create(semester=alice.semester)
    SemesterDownloadFileFactory.create()
    otis.login(alice)
    resp = otis.get_20x("downloads", alice.pk)
    assert list(resp.context["object_list"]) == [download]


@pytest.mark.django_db
def test_download_list_of_other_student_denied(otis) -> None:
    alice = StudentFactory.create()
    otis.login(alice)
    otis.get_40x("downloads", StudentFactory.create().pk)
