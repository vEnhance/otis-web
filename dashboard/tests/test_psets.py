import datetime
import os
from io import StringIO
from typing import Any

import pytest
from freezegun import freeze_time

from core.factories import SemesterFactory, UnitFactory
from core.models import Unit
from dashboard.factories import PSetFactory
from dashboard.models import PSet
from dashboard.utils import get_units_to_submit, get_units_to_unlock
from roster.factories import AssistantFactory, InvoiceFactory, StudentFactory
from roster.models import Student, StudentStanding


def upload(name: str) -> StringIO:
    content = StringIO(name)
    content.name = name
    return content


def pset_data(unit: Unit, **overrides: Any) -> dict[str, Any]:
    return {
        "unit": unit.pk,
        "clubs": 13,
        "hours": 37,
        "feedback": "hello",
        "special_notes": "meow",
        **overrides,
    }


def delinquent_student() -> Student:
    alice = StudentFactory.create(
        semester__show_invoices=True,
        semester__half_payment_deadline=datetime.datetime(
            2021, 7, 1, tzinfo=datetime.UTC
        ),
    )
    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=alice)
    return alice


@pytest.fixture
def alice_with_units() -> tuple[Student, list[Unit]]:
    units = [UnitFactory.create(code=code) for code in ("BMW", "DMX", "ZMY")]
    alice = StudentFactory.create()
    alice.curriculum.set(units)
    alice.unlocked_units.add(units[0])
    return alice, units


@pytest.mark.django_db
def test_submit_denied_when_delinquent(otis) -> None:
    alice = delinquent_student()
    otis.login(alice)
    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("submit-pset", alice.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "student_kwargs",
    [{"standing": StudentStanding.DROPPED}, {"semester__active": False}],
)
def test_submit_denied(otis, student_kwargs) -> None:
    alice = StudentFactory.create(**student_kwargs)
    otis.login(alice)
    otis.get_denied("submit-pset", alice.pk)


@pytest.mark.django_db
def test_submit_page_loads(otis, alice_with_units) -> None:
    alice, _ = alice_with_units
    otis.login(alice)
    assert otis.get_20x("submit-pset", alice.pk).context["title"] == "Ready to submit?"


@pytest.mark.django_db
def test_submit_creates_pending_pset(otis, alice_with_units) -> None:
    alice, units = alice_with_units
    otis.login(alice)

    resp = otis.post_20x(
        "submit-pset",
        alice.pk,
        data=pset_data(
            units[0], content=upload("content1.txt"), next_unit_to_unlock=units[1].pk
        ),
        follow=True,
    )
    otis.assert_testid(resp, "pset-status-pending")
    pset = PSet.objects.get(student=alice, unit=units[0])
    assert resp.context["pset"] == pset
    assert pset.clubs == 13
    assert pset.hours == 37
    assert pset.feedback == "hello"
    assert pset.special_notes == "meow"
    assert pset.next_unit_to_unlock == units[1]
    assert os.path.basename(pset.upload.content.name) == "content1.txt"
    assert not pset.accepted
    assert not pset.resubmitted


@pytest.mark.django_db
def test_pending_pset_does_not_count_toward_level(otis, alice_with_units) -> None:
    alice, units = alice_with_units
    PSetFactory.create(student=alice, unit=units[0], clubs=13, hours=37, status="P")
    otis.login(alice)
    assert otis.get_20x("stats", alice.pk).context["level_number"] == 0


@pytest.mark.django_db
def test_accepted_pset_counts_toward_level(otis, alice_with_units) -> None:
    alice, units = alice_with_units
    pset = PSetFactory.create(
        student=alice, unit=units[0], clubs=13, hours=3.7, status="A"
    )
    otis.login(alice)
    assert otis.get_20x("stats", alice.pk).context["level_number"] == 4
    otis.assert_testid(otis.get_20x("pset", pset.pk), "pset-status-accepted")


@pytest.fixture
def pending_pset(alice_with_units) -> PSet:
    alice, units = alice_with_units
    return PSetFactory.create(
        student=alice,
        unit=units[0],
        clubs=13,
        hours=37,
        feedback="hello",
        special_notes="meow",
        status="P",
        next_unit_to_unlock=units[1],
    )


@pytest.mark.django_db
def test_resubmit_page_shows_current_file(otis, pending_pset) -> None:
    otis.login(pending_pset.student)
    resp = otis.get_20x("resubmit-pset", pending_pset.pk)
    assert resp.context["pset"].filename == pending_pset.filename


@pytest.mark.django_db
def test_resubmit_pending_pset_replaces_file(otis, pending_pset) -> None:
    unit3 = pending_pset.student.curriculum.get(code="ZMY")
    otis.login(pending_pset.student)

    resp = otis.post_20x(
        "resubmit-pset",
        pending_pset.pk,
        data=pset_data(
            pending_pset.unit,
            hours=3.7,
            content=upload("content2.txt"),
            next_unit_to_unlock=unit3.pk,
        ),
        follow=True,
    )
    otis.assert_testid(resp, "pset-status-pending")
    pending_pset.refresh_from_db()
    assert pending_pset.hours == 3.7
    assert pending_pset.next_unit_to_unlock == unit3
    assert os.path.basename(pending_pset.upload.content.name) == "content2.txt"
    assert not pending_pset.accepted
    assert not pending_pset.resubmitted


@pytest.mark.django_db
def test_resubmit_without_file_changes_only_metadata(otis, pending_pset) -> None:
    old_upload = pending_pset.upload
    otis.login(pending_pset.student)

    otis.post_20x(
        "resubmit-pset",
        pending_pset.pk,
        data=pset_data(
            pending_pset.unit,
            feedback="good day",
            special_notes="purr",
            next_unit_to_unlock=pending_pset.next_unit_to_unlock.pk,
        ),
        follow=True,
    )
    pending_pset.refresh_from_db()
    assert pending_pset.feedback == "good day"
    assert pending_pset.special_notes == "purr"
    assert pending_pset.upload == old_upload


@pytest.mark.django_db
def test_resubmit_accepted_pset(otis, alice_with_units) -> None:
    alice, units = alice_with_units
    pset = PSetFactory.create(
        student=alice, unit=units[0], clubs=13, hours=3.7, status="A"
    )
    otis.login(alice)

    otis.post_20x(
        "resubmit-pset",
        pset.pk,
        data=pset_data(units[0], clubs=100, hours=20, content=upload("content3.txt")),
        follow=True,
    )
    otis.assert_testid(otis.get_20x("pset", pset.pk), "pset-status-pending")
    pset.refresh_from_db()
    assert pset.clubs == 100
    assert pset.hours == 20
    assert os.path.basename(pset.upload.content.name) == "content3.txt"
    assert not pset.accepted
    assert pset.resubmitted
    assert otis.get_20x("stats", alice.pk).context["level_number"] == 0


@pytest.fixture
def past_pset() -> PSet:
    alice_past = StudentFactory.create(semester=SemesterFactory.create(active=False))
    return PSetFactory.create(student=alice_past, status="A")


@pytest.mark.django_db
def test_past_semester_pset_cannot_be_resubmitted(otis, past_pset) -> None:
    otis.login(past_pset.student)
    resp = otis.get_20x("pset", past_pset.pk)
    assert resp.context["can_resubmit"] is False
    otis.assert_testid(resp, "pset-semester-inactive")
    otis.get_denied("resubmit-pset", past_pset.pk)


@pytest.mark.django_db
def test_reenrolling_does_not_reopen_past_pset(otis, past_pset) -> None:
    alice_now = StudentFactory.create(user=past_pset.student.user)
    otis.login(alice_now)
    resp = otis.get_20x("pset", past_pset.pk)
    assert resp.context["current_student"] == alice_now
    otis.get_denied("resubmit-pset", past_pset.pk)


@pytest.mark.django_db
def test_same_unit_this_year_can_be_resubmitted(otis, past_pset) -> None:
    alice_now = StudentFactory.create(user=past_pset.student.user)
    new_pset = PSetFactory.create(student=alice_now, unit=past_pset.unit, status="A")
    otis.login(alice_now)
    resp = otis.get_20x("pset", new_pset.pk)
    assert resp.context["can_resubmit"] is True
    otis.assert_no_testid(resp, "pset-semester-inactive")
    otis.get_20x("resubmit-pset", new_pset.pk)


@pytest.mark.django_db
def test_pset_detail_anonymous_redirects_without_leaking(otis) -> None:
    pset = PSetFactory.create(feedback="alice-secret-feedback")
    otis.assert_not_has(
        otis.get_login_redirect("pset", pset.pk), "alice-secret-feedback"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("is_assistant", [False, True])
def test_pset_detail_denied_to_strangers(otis, is_assistant: bool) -> None:
    pset = PSetFactory.create(feedback="alice-secret-feedback")
    stranger = AssistantFactory.create() if is_assistant else StudentFactory.create()
    otis.login(stranger)
    otis.assert_not_has(otis.get_denied("pset", pset.pk), "alice-secret-feedback")


@pytest.mark.django_db
def test_pset_detail_visible_to_owner_and_instructor(otis) -> None:
    instructor = AssistantFactory.create()
    pset = PSetFactory.create(student__assistants=[instructor])
    for user in (pset.student, instructor):
        otis.login(user)
        otis.get_20x("pset", pset.pk)


@pytest.mark.django_db
def test_pset_list_shows_only_own_psets(otis) -> None:
    alice = StudentFactory.create()
    psets = set(PSetFactory.create_batch(2, student=alice))
    PSetFactory.create(student__semester=alice.semester)
    otis.login(alice)
    resp = otis.get_20x("student-pset-list", alice.pk)
    assert set(resp.context["object_list"]) == psets


@pytest.mark.django_db
def test_pset_list_denied_when_delinquent(otis) -> None:
    alice = delinquent_student()
    otis.login(alice)
    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("student-pset-list", alice.pk)


@pytest.mark.django_db
def test_pset_list_of_other_student_denied(otis) -> None:
    alice = StudentFactory.create()
    otis.login(StudentFactory.create(semester=alice.semester))
    otis.get_denied("student-pset-list", alice.pk)


@pytest.mark.django_db
def test_units_to_submit_and_unlock() -> None:
    units = UnitFactory.create_batch(size=20)
    alice = StudentFactory.create()
    alice.curriculum.set(units[:18])
    alice.unlocked_units.set(units[4:7])
    for unit in units[:4]:
        PSetFactory.create(student=alice, unit=unit)
    PSetFactory.create(student=alice, unit=units[4], status="P")

    assert set(get_units_to_submit(alice)) == {units[5], units[6]}
    assert set(get_units_to_unlock(alice)) == set(units[7:18])
