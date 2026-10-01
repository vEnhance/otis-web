import csv
import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.messages import constants as message_levels
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun.api import freeze_time

from core.factories import SemesterFactory, UserFactory
from core.models import Semester
from roster.factories import AssistantFactory, InvoiceFactory, StudentFactory
from roster.models import Invoice, Student, StudentStanding
from roster.utils import annotate_payment_status
from roster.views import get_late_fee_targets

UTC = datetime.UTC
HALF_DEADLINE = datetime.datetime(2022, 9, 21, tzinfo=UTC)
FULL_DEADLINE = datetime.datetime(2023, 1, 21, tzinfo=UTC)


def invoiced_student(
    created: str = "2022-08-05", preps_taught: int = 2, **semester_kwargs
) -> Student:
    semester = SemesterFactory.create(
        show_invoices=True,
        half_payment_deadline=HALF_DEADLINE,
        full_payment_deadline=FULL_DEADLINE,
        **semester_kwargs,
    )
    student = StudentFactory.create(semester=semester)
    with freeze_time(created, tz_offset=0):
        InvoiceFactory.create(student=student, preps_taught=preps_taught)
    return student


def set_invoice(student: Student, **fields) -> None:
    invoice = student.invoice
    for field, value in fields.items():
        setattr(invoice, field, value)
    invoice.save()


def annotated_payment_status(student: Student) -> int:
    queryset = annotate_payment_status(Student.objects.filter(pk=student.pk))
    return queryset.get().payment_status_code  # type: ignore


@pytest.mark.django_db
def test_invoice_total_and_checksum(otis) -> None:
    alice = StudentFactory.create(semester__show_invoices=True)
    InvoiceFactory.create(
        student=alice,
        preps_taught=2,
        hours_taught=8.4,
        adjustment=-30,
        credits=70,
        extras=100,
        total_paid=400,
    )
    otis.login(alice)
    response = otis.get("invoice", follow=True)
    assert response.context["invoice"].total_owed == Decimal("752.00")
    checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
    assert len(checksum) == 36
    assert response.context["checksum"] == checksum


EDIT_INVOICE_DATA = {
    "preps_taught": 2,
    "hours_taught": 8.4,
    "adjustment": 0,
    "extras": 0,
    "total_paid": 1152,
    "credits": 0,
}


@pytest.fixture
def instructor_invoice() -> Invoice:
    firefly = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[firefly], semester__show_invoices=True)
    return InvoiceFactory.create(student=alice, total_paid=0)


@pytest.mark.django_db
def test_instructor_cannot_edit_invoice(otis, instructor_invoice) -> None:
    alice = instructor_invoice.student
    otis.login(alice.assistants.get())
    otis.assert_no_testid(otis.get_20x("invoice", alice.pk), "edit-invoice-link")
    otis.get_denied("edit-invoice", instructor_invoice.pk)
    otis.post_denied("edit-invoice", instructor_invoice.pk, data=EDIT_INVOICE_DATA)
    instructor_invoice.refresh_from_db()
    assert instructor_invoice.total_paid == 0


@pytest.mark.django_db
def test_superuser_edits_invoice(otis, instructor_invoice) -> None:
    alice = instructor_invoice.student
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.assert_testid(otis.get_20x("invoice", alice.pk), "edit-invoice-link")
    otis.get_20x("edit-invoice", instructor_invoice.pk)
    otis.post_redirects(
        otis.url("invoice", alice.pk),
        "edit-invoice",
        instructor_invoice.pk,
        data=EDIT_INVOICE_DATA,
    )
    instructor_invoice.refresh_from_db()
    assert instructor_invoice.preps_taught == 2
    assert instructor_invoice.total_paid == 1152


@pytest.mark.django_db
def test_payment_status_without_invoice() -> None:
    alice = StudentFactory.create(
        semester__show_invoices=True,
        semester__half_payment_deadline=HALF_DEADLINE,
    )
    assert alice.payment_status == 0
    assert annotated_payment_status(alice) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("total_paid", "credits", "stamp", "status"),
    [
        # nothing paid: reminded, then warned, then locked at the half deadline
        (0, 0, "2022-09-05", 1),
        (0, 0, "2022-09-17", 1),
        (0, 0, "2022-09-22", 2),
        (0, 0, "2022-10-15", 3),
        (0, 0, "2022-11-15", 3),
        # less than half still counts against the half deadline
        (239, 0, "2022-09-22", 2),
        (239, 0, "2022-10-15", 3),
        # half paid: clear until the full deadline approaches
        (240, 0, "2022-09-05", 4),
        (240, 0, "2022-10-15", 4),
        (240, 0, "2022-12-30", 5),
        (240, 0, "2023-01-17", 5),
        (240, 0, "2023-01-22", 6),
        (240, 0, "2023-02-15", 7),
        (240, 0, "2023-06-05", 7),
        # anything short of payment in full is late at the full deadline
        (400, 0, "2023-02-15", 7),
        (480, 0, "2023-02-15", 0),
        # credits count as payment
        (39, 200, "2022-10-15", 3),
        (40, 200, "2022-10-15", 4),
        (40, 200, "2023-02-15", 7),
        (0, 480, "2023-02-15", 0),
    ],
)
def test_payment_status(total_paid: int, credits: int, stamp: str, status: int) -> None:
    alice = invoiced_student()
    set_invoice(alice, total_paid=total_paid, credits=credits)
    with freeze_time(stamp, tz_offset=0):
        assert alice.payment_status == status
        assert alice.is_delinquent is (status in (3, 7))
        assert annotated_payment_status(alice) == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stamp", "status"),
    [("2023-01-23", 1), ("2023-01-24", 2), ("2023-01-26", 3)],
)
def test_payment_status_for_late_joiner(stamp: str, status: int) -> None:
    """Joining after the deadline makes the invoice date the deadline."""
    bob = invoiced_student(created="2023-01-23", preps_taught=1)
    with freeze_time(stamp, tz_offset=0):
        assert bob.payment_status == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stamp", "status"),
    [("2023-01-02", 1), ("2023-01-20", 1), ("2023-01-22", 2), ("2023-01-30", 3)],
)
def test_payment_status_for_second_semester_joiner(stamp: str, status: int) -> None:
    """Joining after one_semester_date pushes the first payment to the full
    deadline."""
    bob = invoiced_student(
        created="2023-01-01",
        preps_taught=1,
        one_semester_date=datetime.datetime(2022, 12, 30, tzinfo=UTC),
    )
    with freeze_time(stamp, tz_offset=0):
        assert bob.payment_status == status
        assert annotated_payment_status(bob) == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("total_paid", "forgive_date", "stamp", "status"),
    [
        (0, datetime.datetime(2022, 11, 1, tzinfo=UTC), "2022-10-15", 1),
        (0, datetime.datetime(2022, 11, 1, tzinfo=UTC), "2022-11-02", 2),
        (0, datetime.datetime(2022, 11, 1, tzinfo=UTC), "2022-11-05", 3),
        (240, datetime.datetime(2023, 3, 1, tzinfo=UTC), "2023-01-01", 4),
        (240, datetime.datetime(2023, 3, 1, tzinfo=UTC), "2023-02-15", 5),
        (240, datetime.datetime(2023, 3, 1, tzinfo=UTC), "2023-03-02", 6),
        (240, datetime.datetime(2023, 3, 1, tzinfo=UTC), "2023-03-04", 7),
    ],
)
def test_forgive_date_extends_deadline(
    total_paid: int, forgive_date: datetime.datetime, stamp: str, status: int
) -> None:
    alice = invoiced_student()
    set_invoice(alice, total_paid=total_paid, forgive_date=forgive_date)
    with freeze_time(stamp, tz_offset=0):
        assert alice.payment_status == status
        assert annotated_payment_status(alice) == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("total_paid", "credits", "extras", "forgive_date"),
    [
        (0, 0, 0, None),
        (239, 0, 0, None),
        (240, 0, 0, None),
        (40, 200, 0, None),
        (240, 0, 60, None),
        (480, 0, 0, None),
        (0, 0, 0, datetime.datetime(2023, 1, 30, tzinfo=UTC)),
    ],
)
def test_payment_status_annotation_agrees_with_property(
    total_paid: int,
    credits: int,
    extras: int,
    forgive_date: datetime.datetime | None,
) -> None:
    """The SQL mirror in annotate_payment_status must agree with the property."""
    one_semester_date = datetime.datetime(2022, 12, 30, tzinfo=UTC)
    alice = invoiced_student(one_semester_date=one_semester_date)
    bob = StudentFactory.create(semester=alice.semester)
    with freeze_time("2023-01-01", tz_offset=0):
        InvoiceFactory.create(student=bob, preps_taught=1)
    set_invoice(
        alice,
        total_paid=total_paid,
        credits=credits,
        extras=extras,
        forgive_date=forgive_date,
    )

    for stamp in (
        "2022-09-17",
        "2022-09-22",
        "2022-10-15",
        "2022-12-30",
        "2023-01-17",
        "2023-01-22",
        "2023-02-15",
    ):
        with freeze_time(stamp, tz_offset=0):
            for student in (alice, bob):
                assert annotated_payment_status(student) == student.payment_status, (
                    student.pk,
                    stamp,
                )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "semester_kwargs",
    [
        {"show_invoices": False},
        {"show_invoices": True},
        {"half_payment_deadline": HALF_DEADLINE},
        {"full_payment_deadline": FULL_DEADLINE},
    ],
)
def test_payment_status_annotation_without_deadlines(semester_kwargs) -> None:
    semester = SemesterFactory.create(**{"show_invoices": True, **semester_kwargs})
    student = StudentFactory.create(semester=semester)
    with freeze_time("2022-08-05", tz_offset=0):
        InvoiceFactory.create(student=student, preps_taught=2)
    with freeze_time("2023-02-15", tz_offset=0):
        assert annotated_payment_status(student) == student.payment_status


@pytest.fixture
def late_fee_roster() -> dict[str, Student]:
    """Students from 2020, now long overdue, of whom only deadbeat, halfway
    and quitter should be charged a late fee."""
    deadlines = {
        "half_payment_deadline": datetime.datetime(2020, 9, 21, tzinfo=UTC),
        "full_payment_deadline": datetime.datetime(2021, 1, 21, tzinfo=UTC),
    }
    semester: Semester = SemesterFactory.create(show_invoices=True, **deadlines)
    past: Semester = SemesterFactory.create(
        show_invoices=True, active=False, **deadlines
    )
    invoices: dict[str, tuple[dict, dict]] = {
        "deadbeat": ({}, {}),
        "halfway": ({}, {"total_paid": 240, "memo": "paid by check"}),
        "cleared": ({}, {"total_paid": 480}),
        "impostor": ({"standing": StudentStanding.FAKE}, {}),
        "alumnus": ({"semester": past}, {}),
        "forgiven": (
            {},
            {"forgive_date": datetime.datetime(2099, 1, 1, tzinfo=UTC)},
        ),
        "springling": ({"standing": StudentStanding.DROPPED}, {"preps_taught": 1}),
        "quitter": ({"standing": StudentStanding.DROPPED}, {}),
    }
    roster: dict[str, Student] = {}
    with freeze_time("2020-08-05", tz_offset=0):
        for name, (student_kwargs, invoice_kwargs) in invoices.items():
            student = StudentFactory.create(**{"semester": semester, **student_kwargs})
            InvoiceFactory.create(
                student=student, **{"preps_taught": 2, **invoice_kwargs}
            )
            roster[name] = student
    return roster


CHARGED = ("deadbeat", "halfway", "quitter")


def login_admin(otis) -> None:
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))


@pytest.mark.django_db
def test_late_fee_roster_statuses(late_fee_roster) -> None:
    assert {name: s.payment_status for name, s in late_fee_roster.items()} == {
        "deadbeat": 3,
        "halfway": 7,
        "cleared": 0,
        "impostor": 3,
        "alumnus": 3,
        "forgiven": 1,
        "springling": 3,
        "quitter": 3,
    }


@pytest.mark.django_db
def test_delinquents_requires_superuser(otis, late_fee_roster) -> None:
    otis.login(StudentFactory.create())
    otis.get_denied("delinquents")
    otis.login(UserFactory.create(is_staff=True))
    otis.get_denied("delinquents")
    otis.post_denied("delinquents", data={"amount": 60, "confirmed": "on"})
    assert not Invoice.objects.filter(extras__gt=0).exists()


@pytest.mark.django_db
def test_delinquents_lists_students_to_charge(otis, late_fee_roster) -> None:
    login_admin(otis)
    resp = otis.get_ok("delinquents")
    assert {s.pk: s.payment_status_code for s in resp.context["students"]} == {
        late_fee_roster["deadbeat"].pk: 3,
        late_fee_roster["halfway"].pk: 7,
        late_fee_roster["quitter"].pk: 3,
    }


@pytest.mark.django_db
def test_delinquents_csv_preview(otis, late_fee_roster) -> None:
    login_admin(otis)
    # an export: its rendered text is the product
    resp = otis.get_ok("delinquents", data={"format": "csv"})
    assert resp.headers["Content-Type"] == "text/csv"
    rows = {
        int(row["Student pk"]): row
        for row in csv.DictReader(StringIO(resp.content.decode()))
    }
    assert set(rows) == {late_fee_roster[name].pk for name in CHARGED}
    halfway = rows[late_fee_roster["halfway"].pk]
    assert halfway["Payment status"] == "7"
    assert halfway["Total cost"] == "480.00"
    assert halfway["Total paid"] == "240.00"
    assert halfway["Total owed"] == "240.00"
    assert halfway["Prep total"] == "480"


@pytest.mark.django_db
def test_delinquents_unconfirmed_is_dry_run(otis, late_fee_roster) -> None:
    login_admin(otis)
    otis.post_ok("delinquents", data={"amount": 60})
    assert not Invoice.objects.filter(extras__gt=0).exists()


@pytest.mark.django_db
def test_delinquents_charges_late_fee(otis, late_fee_roster) -> None:
    login_admin(otis)
    resp = otis.post("delinquents", data={"amount": 60, "confirmed": "on"}, follow=True)
    otis.assert_redirects(resp, otis.url("delinquents"))
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])

    invoices = {
        name: Invoice.objects.get(student=student)
        for name, student in late_fee_roster.items()
    }
    for name, invoice in invoices.items():
        assert invoice.extras == (60 if name in CHARGED else 0), name
    today = timezone.localdate()
    assert invoices["deadbeat"].memo == f"{today}: late fee of $60"
    assert invoices["halfway"].memo == f"paid by check\n{today}: late fee of $60"
    assert invoices["cleared"].memo == ""


@pytest.mark.django_db
def test_late_fee_is_one_plain_update(otis, late_fee_roster) -> None:
    # MySQL rejects an UPDATE whose WHERE clause reads the table being updated,
    # so the charge must name roster_invoice only as the target
    login_admin(otis)
    with CaptureQueriesContext(connection) as captured:
        otis.post("delinquents", data={"amount": 60, "confirmed": "on"})
    updates = [
        q["sql"]
        for q in captured
        if q["sql"].lstrip().upper().startswith("UPDATE")
        and "roster_invoice" in q["sql"]
    ]
    assert len(updates) == 1
    assert "SELECT" not in updates[0].upper()


@pytest.mark.django_db
def test_delinquents_with_nobody_overdue(otis) -> None:
    SemesterFactory.create(show_invoices=True)
    login_admin(otis)
    resp = otis.get_ok("delinquents")
    assert not resp.context["students"]
    otis.assert_testid(resp, "late-fee-nobody")


@pytest.mark.django_db
def test_late_fee_targets_in_one_query(django_assert_num_queries) -> None:
    semester = SemesterFactory.create(
        show_invoices=True,
        half_payment_deadline=datetime.datetime(2020, 9, 21, tzinfo=UTC),
        full_payment_deadline=datetime.datetime(2021, 1, 21, tzinfo=UTC),
    )
    with freeze_time("2020-08-05", tz_offset=0):
        for _ in range(10):
            InvoiceFactory.create(
                student=StudentFactory.create(semester=semester), preps_taught=2
            )

    with django_assert_num_queries(1):
        students = list(get_late_fee_targets())
        for student in students:
            assert student.invoice.prep_total > 0
            assert student.name
    assert len(students) == 10
