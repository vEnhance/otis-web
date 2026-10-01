import datetime
from io import StringIO
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
import tablib
from django.contrib.auth.models import Group, User
from django.contrib.messages import constants as message_levels
from freezegun.api import freeze_time

from core.factories import SemesterFactory, UserFactory
from core.models import Semester, UserProfile
from roster.admin import ApplyUUIDIEResource
from roster.factories import (
    ApplyUUIDFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from roster.models import (
    ApplyUUID,
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    build_student,
)


def registration_data(passcode: Any, **overrides: Any) -> dict[str, Any]:
    agreement = StringIO("agree!")
    agreement.name = "agreement.pdf"
    return {
        "given_name": "Alice",
        "surname": "Aardvark",
        "email_address": "myemail@example.com",
        "passcode": passcode,
        "gender": "O",
        "parent_email": "parent@example.com",
        "graduation_year": 0,
        "school_name": "Generic School District",
        "country": "USA",
        "us_state": "MA",
        "aops_username": "",
        "agreement_form": agreement,
        "email_on_announcement": False,
        "email_on_pset_complete": True,
        "email_on_suggestion_processed": False,
        "email_on_petition_complete": False,
        **overrides,
    }


@pytest.fixture
def container() -> RegistrationContainer:
    return RegistrationContainerFactory.create(accepting_responses=True)


@pytest.fixture
def alice(otis) -> User:
    return otis.login(
        UserFactory.create(first_name="a", last_name="a", email="a@a.net")
    )


@pytest.mark.django_db
def test_register_without_container(otis, alice) -> None:
    otis.assert_message(
        otis.get_20x("register", follow=True),
        "Registration is not set up on the website yet.",
    )


@pytest.mark.django_db
def test_register_while_not_accepting(otis, alice) -> None:
    RegistrationContainerFactory.create()
    otis.assert_message(
        otis.get_20x("register", follow=True),
        "This semester isn't accepting registration yet.",
    )


@pytest.mark.django_db
def test_register_page_loads(otis, alice, container) -> None:
    resp = otis.get_20x("register")
    otis.assert_no_messages(resp)
    assert resp.context["container"] == container


@pytest.mark.django_db
def test_register_prefills_from_old_registration(otis, alice, container) -> None:
    StudentRegistrationFactory.create(
        user=alice,
        parent_email="mom@example.com",
        container__semester__active=False,
    )
    resp = otis.get_20x("register")
    otis.assert_no_messages(resp)
    assert resp.context["form"].initial["parent_email"] == "mom@example.com"


@pytest.mark.django_db
def test_register_wrong_passcode(otis, alice, container) -> None:
    otis.assert_message(
        otis.post_20x("register", data=registration_data(uuid4()), follow=True),
        "Wrong passcode",
    )
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
def test_register_malformed_passcode(otis, alice, container) -> None:
    otis.assert_message(
        otis.post_20x("register", data=registration_data("MEOW"), follow=True),
        "Wrong passcode",
    )
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
def test_register_empty_post(otis, alice, container) -> None:
    resp = otis.post_20x("register")
    assert resp.context["form"].errors
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
def test_register(otis, alice, container) -> None:
    au = ApplyUUIDFactory.create(percent_aid=0)
    resp = otis.post_20x("register", data=registration_data(au.uuid), follow=True)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])

    reg = StudentRegistration.objects.get(user=alice, container=container)
    au.refresh_from_db()
    assert au.reg == reg
    student = Student.objects.get(user=alice)
    assert student.semester == container.semester
    assert student.reg == reg
    assert Invoice.objects.get(student=student).total_owed == 480
    assert Group.objects.get(name="Verified") in alice.groups.all()


@pytest.mark.django_db
def test_register_updates_user(otis, alice, container) -> None:
    au = ApplyUUIDFactory.create()
    otis.post_20x("register", data=registration_data(au.uuid), follow=True)

    alice.refresh_from_db()
    assert alice.first_name == "Alice"
    assert alice.last_name == "Aardvark"
    assert alice.email == "myemail@example.com"
    profile = UserProfile.objects.get(user=alice)
    assert not profile.email_on_announcement
    assert profile.email_on_pset_complete
    assert not profile.email_on_suggestion_processed
    assert not profile.email_on_petition_complete


@pytest.mark.django_db
def test_register_applies_financial_aid(otis, alice, container) -> None:
    au = ApplyUUIDFactory.create(percent_aid=70)
    otis.post_20x("register", data=registration_data(au.uuid), follow=True)
    assert Invoice.objects.get(student__user=alice).total_owed == 144


@pytest.mark.django_db
def test_register_twice(otis, alice, container) -> None:
    StudentRegistrationFactory.create(user=alice, container=container)
    au = ApplyUUIDFactory.create()
    otis.assert_message(
        otis.post_20x("register", data=registration_data(au.uuid), follow=True),
        "You have already submitted a decision form for this year!",
    )
    au.refresh_from_db()
    assert au.reg is None


@pytest.mark.django_db
def test_register_with_used_passcode(otis, container) -> None:
    au = ApplyUUIDFactory.create(
        reg=StudentRegistrationFactory.create(container=container)
    )
    bob = otis.login(UserFactory.create())
    otis.post_40x("register", data=registration_data(au.uuid), follow=True)
    assert not StudentRegistration.objects.filter(user=bob).exists()


@pytest.mark.django_db
def test_register_with_disabled_passcode(otis, alice, container) -> None:
    au = ApplyUUIDFactory.create(enabled=False)
    resp = otis.post_20x("register", data=registration_data(au.uuid), follow=True)
    assert any(m.level == message_levels.ERROR for m in resp.context["messages"])
    assert not StudentRegistration.objects.filter(user=alice).exists()
    au.refresh_from_db()
    assert au.reg is None


@pytest.mark.django_db
def test_register_is_all_or_nothing(otis, alice, container) -> None:
    """A failure partway through redemption leaves the passcode unspent."""
    au = ApplyUUIDFactory.create()
    with (
        mock.patch("roster.views.build_student", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        otis.post("register", data=registration_data(au.uuid))

    au.refresh_from_db()
    assert au.reg is None
    assert not StudentRegistration.objects.filter(user=alice).exists()
    assert not Student.objects.filter(user=alice).exists()
    alice.refresh_from_db()
    assert alice.first_name == "a"


@pytest.mark.django_db
@pytest.mark.parametrize(("country", "us_state"), [("USA", ""), ("CAN", "MA")])
def test_register_rejects_mismatched_us_state(
    otis, alice, container, country: str, us_state: str
) -> None:
    au = ApplyUUIDFactory.create()
    resp = otis.post_20x(
        "register",
        data=registration_data(au.uuid, country=country, us_state=us_state),
    )
    assert "us_state" in resp.context["form"].errors
    assert not StudentRegistration.objects.filter(user=alice).exists()


@pytest.mark.django_db
def test_register_abroad_without_us_state(otis, alice, container) -> None:
    au = ApplyUUIDFactory.create()
    otis.post_20x(
        "register",
        data=registration_data(au.uuid, country="CAN", us_state=""),
        follow=True,
    )
    assert StudentRegistration.objects.get(user=alice).us_state == ""


@pytest.mark.django_db
def test_backfill_us_state_requires_choice(otis) -> None:
    reg = StudentRegistrationFactory.create()
    otis.login(reg.user)
    otis.assert_message(
        otis.post_20x("backfill-us-state", data={"us_state": ""}, follow=True),
        "Please choose a state from the dropdown.",
    )
    reg.refresh_from_db()
    assert reg.us_state == ""


@pytest.mark.django_db
def test_backfill_us_state_fills_every_us_registration(otis) -> None:
    alice = UserFactory.create()
    old_reg = StudentRegistrationFactory.create(user=alice)
    new_reg = StudentRegistrationFactory.create(user=alice)
    abroad_reg = StudentRegistrationFactory.create(user=alice, country="FRA")
    bob_reg = StudentRegistrationFactory.create()
    otis.login(alice)

    resp = otis.post_20x("backfill-us-state", data={"us_state": "NY"}, follow=True)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    for reg, us_state in (
        (old_reg, "NY"),
        (new_reg, "NY"),
        (abroad_reg, ""),
        (bob_reg, ""),
    ):
        reg.refresh_from_db()
        assert reg.us_state == us_state


@pytest.mark.django_db
def test_backfill_us_state_when_already_on_file(otis) -> None:
    reg = StudentRegistrationFactory.create(us_state="NY")
    otis.login(reg.user)
    otis.assert_message(
        otis.post_20x("backfill-us-state", data={"us_state": "TX"}, follow=True),
        "Your state is already on file, nothing to do here.",
    )
    reg.refresh_from_db()
    assert reg.us_state == "NY"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stamp", "total_owed"), [("2023-08-01", 480), ("2024-01-01", 240)]
)
def test_build_student_bills_by_semesters_left(stamp: str, total_owed: int) -> None:
    semester: Semester = SemesterFactory.create(
        one_semester_date=datetime.datetime(2023, 12, 25, tzinfo=datetime.UTC),
    )
    container = RegistrationContainerFactory.create(semester=semester)
    with freeze_time(stamp, tz_offset=0):
        alice = build_student(StudentRegistrationFactory.create(container=container))
        assert alice.invoice.total_owed == total_owed


@pytest.mark.django_db
def test_applyuuid_admin_pages_load(otis) -> None:
    otis.login(UserFactory.create(is_superuser=True, is_staff=True))
    otis.get_20x("admin:roster_applyuuid_export")
    otis.get_20x("admin:roster_applyuuid_import")


def test_applyuuid_export_omits_id() -> None:
    # rows are matched on the unique `uuid`, and an importable `id` column
    # would let a CSV reassign an existing row's primary key
    assert ApplyUUIDIEResource().get_export_headers() == [
        "uuid",
        "percent_aid",
        "enabled",
        "created_at",
        "registered_at",
        "applicant_name",
    ]


def import_applyuuids(headers: list[str], *rows: list[Any]):
    dataset = tablib.Dataset(headers=headers)
    for row in rows:
        dataset.append(row)
    result = ApplyUUIDIEResource().import_data(dataset, raise_errors=True)
    assert not result.has_errors()
    return result


@pytest.mark.django_db
def test_applyuuid_import_creates_row() -> None:
    uuid = str(uuid4())
    result = import_applyuuids(["uuid", "percent_aid"], [uuid, 30])
    assert result.totals["new"] == 1
    assert ApplyUUID.objects.get(uuid=uuid).percent_aid == 30


@pytest.mark.django_db
def test_applyuuid_reimport_updates_in_place() -> None:
    au = ApplyUUIDFactory.create(percent_aid=40)
    original_pk = au.pk
    result = import_applyuuids(["uuid", "percent_aid"], [str(au.uuid), 55])
    assert result.totals["update"] == 1
    au.refresh_from_db()
    assert au.percent_aid == 55
    assert au.pk == original_pk
    assert ApplyUUID.objects.count() == 1


@pytest.mark.django_db
def test_applyuuid_import_ignores_created_at() -> None:
    au = ApplyUUIDFactory.create(percent_aid=40)
    original_created_at = au.created_at
    import_applyuuids(
        ["uuid", "percent_aid", "created_at"],
        [str(au.uuid), 60, "2000-01-01 00:00:00"],
    )
    au.refresh_from_db()
    assert au.percent_aid == 60
    assert au.created_at == original_created_at


@pytest.mark.django_db
def test_apply_uuid_lookup_redirects_to_application(otis) -> None:
    reg = StudentRegistrationFactory.create()
    student = StudentFactory.create(reg=reg)
    au = ApplyUUIDFactory.create(reg=reg)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.get_redirects(
        f"https://apply.evanchen.cc/{au.uuid}", "apply-uuid-lookup", student.pk
    )


@pytest.mark.django_db
def test_apply_uuid_lookup_without_passcode(otis) -> None:
    student = StudentFactory.create(reg=StudentRegistrationFactory.create())
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.get_not_found("apply-uuid-lookup", student.pk)


@pytest.mark.django_db
def test_apply_uuid_lookup_without_registration(otis) -> None:
    student = StudentFactory.create()
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.get_not_found("apply-uuid-lookup", student.pk)


@pytest.mark.django_db
def test_apply_uuid_lookup_requires_superuser(otis) -> None:
    reg = StudentRegistrationFactory.create()
    student = StudentFactory.create(reg=reg)
    ApplyUUIDFactory.create(reg=reg)
    otis.login(UserFactory.create(is_staff=True))
    otis.get_denied("apply-uuid-lookup", student.pk)
