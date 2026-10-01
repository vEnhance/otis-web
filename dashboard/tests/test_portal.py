import datetime

import pytest
from django.conf import settings
from django.contrib.messages import constants as message_levels
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from freezegun import freeze_time

from core.factories import (
    UnitFactory,
    UnitGroupFactory,
    UserFactory,
)
from core.models import Unit, UnitGroup
from dashboard.factories import AnnouncementFactory, PSetFactory
from exams.factories import PracticeExamFactory, QuizFactory
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from roster.models import Student, StudentStanding
from rpg.factories import BonusLevelFactory
from rpg.models import Level

UTC = datetime.UTC


@pytest.mark.django_db
def test_portal_redirects_delinquent_to_invoice(otis) -> None:
    alice = StudentFactory.create(
        semester__show_invoices=True,
        semester__half_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
    )
    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=alice)
    otis.login(alice)
    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_redirects(
            reverse("invoice", args=(alice.pk,)), "portal", alice.pk, follow=True
        )


@pytest.mark.django_db
def test_portal_context(otis) -> None:
    alice = StudentFactory.create(semester__exam_family="Waltz")
    unit = UnitFactory.create(code="BMX")
    alice.curriculum.set([unit])
    alice.unlocked_units.add(unit)
    PSetFactory.create(student=alice, clubs=501, hours=0, status="A", unit=unit)
    StudentFactory.create(user=alice.user, semester__end_year=2020)
    exam_dates = {
        "start_date": datetime.datetime(2021, 6, 1, tzinfo=UTC),
        "due_date": datetime.datetime(2021, 7, 31, tzinfo=UTC),
        "family": "Waltz",
        "number": 1,
    }
    test = PracticeExamFactory.create(**exam_dates)
    quiz = QuizFactory.create(**exam_dates)
    otis.login(alice)

    with freeze_time("2021-07-01", tz_offset=0):
        resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["title"] == f"{alice.name} ({alice.semester.name})"
    assert resp.context["level_number"] == 22
    assert resp.context["meters"]["clubs"].value == 501
    assert 2020 in [row["semester__end_year"] for row in resp.context["history"]]
    assert [row["unit"] for row in resp.context["curriculum"]] == [unit]
    assert list(resp.context["tests"]) == [test]
    assert list(resp.context["quizzes"]) == [quiz]


@pytest.fixture
def alice_at_level_22() -> Student:
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    PSetFactory.create(student=alice, clubs=501, hours=0, status="A", unit__code="BMX")
    return alice


@pytest.mark.django_db
def test_portal_levels_up_student(otis, alice_at_level_22) -> None:
    alice = alice_at_level_22
    otis.login(alice)
    resp = otis.get_20x("portal", alice.pk, follow=True)
    alice.refresh_from_db()
    assert alice.last_level_seen == 22
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])


@pytest.mark.django_db
def test_portal_seen_by_instructor_does_not_level_up(otis, alice_at_level_22) -> None:
    alice = alice_at_level_22
    otis.login(alice.assistants.get())
    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["level_number"] == 22
    assert not resp.context["messages"]
    alice.refresh_from_db()
    assert alice.last_level_seen != 22


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("standing", "shown", "hidden"),
    [
        (StudentStanding.SUSPENDED, "portal-suspended-alert", "portal-probation-alert"),
        (StudentStanding.PROBATION, "portal-probation-alert", "portal-suspended-alert"),
    ],
)
def test_portal_standing_alert_for_admin(
    otis, standing: StudentStanding, shown: str, hidden: str
) -> None:
    alice = StudentFactory.create(standing=standing)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    resp = otis.get_ok("portal", alice.pk)
    otis.assert_testid(resp, shown)
    otis.assert_no_testid(resp, hidden)


@pytest.mark.django_db
def test_portal_hides_probation_from_student(otis) -> None:
    alice = StudentFactory.create(standing=StudentStanding.PROBATION)
    otis.login(alice)
    resp = otis.get_ok("portal", alice.pk)
    otis.assert_no_testid(resp, "portal-probation-alert")
    otis.assert_no_testid(resp, "portal-suspended-alert")


@pytest.mark.django_db
def test_portal_fetches_profile_once(otis) -> None:
    alice = StudentFactory.create()
    otis.login(alice)
    otis.get_20x("portal", alice.pk, follow=True)

    with CaptureQueriesContext(connection) as ctx:
        otis.get_20x("portal", alice.pk, follow=True)
    profile_queries = [
        q for q in ctx.captured_queries if "core_userprofile" in q["sql"]
    ]
    assert len(profile_queries) == 1, profile_queries


@pytest.mark.django_db
def test_portal_dismiss_news(otis) -> None:
    alice = StudentFactory.create()
    AnnouncementFactory.create()
    otis.login(alice)

    assert otis.get_20x("portal", alice.pk, follow=True).context["num_news"] == 1
    otis.post_redirects(otis.url("portal", alice.pk), "dismiss-news", alice.pk)
    assert otis.get_20x("portal", alice.pk, follow=True).context["num_news"] == 0


@pytest.fixture
def alice_missing_us_state() -> Student:
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    StudentRegistrationFactory.create(user=alice.user, country="USA")
    return alice


@pytest.mark.django_db
def test_portal_us_state_alert(otis, alice_missing_us_state) -> None:
    alice = alice_missing_us_state
    otis.login(alice)
    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["us_state_form"] is not None
    otis.assert_testid(resp, "us-state-alert")


@pytest.mark.django_db
def test_portal_us_state_alert_shown_to_instructor(
    otis, alice_missing_us_state
) -> None:
    alice = alice_missing_us_state
    otis.login(alice.assistants.get())
    otis.assert_testid(otis.get_20x("portal", alice.pk, follow=True), "us-state-alert")


@pytest.mark.django_db
def test_portal_us_state_alert_gone_once_filled(otis) -> None:
    alice = StudentFactory.create()
    StudentRegistrationFactory.create(user=alice.user, country="USA", us_state="NY")
    otis.login(alice)
    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["us_state_form"] is None
    otis.assert_no_testid(resp, "us-state-alert")


@pytest.fixture
def bonus_groups() -> list[UnitGroup]:
    """Secret groups for bonus levels 4, 9 and 16, each with three units."""
    groups = []
    for level in (4, 9, 16):
        group = UnitGroupFactory.create(name=f"Level {level}", subject="K", hidden=True)
        for code in ("BKV", "DKV", "ZKV"):
            UnitFactory.create(code=code, group=group)
        BonusLevelFactory.create(level=level, group=group)
        groups.append(group)
    return groups


@pytest.mark.django_db
def test_no_bonus_levels_before_reaching_them(otis, bonus_groups) -> None:
    alice = StudentFactory.create()
    otis.login(alice)

    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert not resp.context["bonus_levels"]
    otis.assert_no_testid(resp, "bonus-level-request")

    resp = otis.get_20x("bonus-level-request", alice.pk)
    assert not resp.context["form"].fields["unit"].queryset.exists()
    otis.assert_message(resp, "There are no secret units you can request yet.")


@pytest.mark.django_db
def test_level_up_adds_bonus_units(otis, bonus_groups) -> None:
    alice = StudentFactory.create()
    PSetFactory.create(student=alice, clubs=13, hours=37, status="A", unit__code="BCY")
    otis.login(alice)

    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["bonus_levels"]
    otis.assert_testid(resp, "bonus-level-request")
    alice.refresh_from_db()
    assert alice.last_level_seen == 9
    assert set(alice.curriculum.all()) == {
        Unit.objects.get(group=group, code="BKV") for group in bonus_groups[:2]
    }


@pytest.mark.django_db
def test_bonus_request_offers_reached_levels(otis, bonus_groups) -> None:
    alice = StudentFactory.create(last_level_seen=9)
    otis.login(alice)
    resp = otis.get_20x("bonus-level-request", alice.pk)
    otis.assert_no_messages(resp)
    assert set(resp.context["form"].fields["unit"].queryset) == set(
        Unit.objects.filter(group__in=bonus_groups[:2])
    )


@pytest.mark.django_db
def test_bonus_request_adds_unit(otis, bonus_groups) -> None:
    alice = StudentFactory.create(last_level_seen=9)
    desired_unit = Unit.objects.get(group=bonus_groups[1], code="DKV")
    otis.login(alice)
    otis.post_20x("bonus-level-request", alice.pk, data={"unit": desired_unit.pk})
    assert alice.curriculum.contains(desired_unit)


@pytest.mark.django_db
def test_bonus_request_refuses_unreached_level(otis, bonus_groups) -> None:
    alice = StudentFactory.create(last_level_seen=9)
    unit = Unit.objects.get(group=bonus_groups[2], code="DKV")
    otis.login(alice)
    resp = otis.post_20x("bonus-level-request", alice.pk, data={"unit": unit.pk})
    assert "unit" in resp.context["form"].errors
    assert not alice.curriculum.contains(unit)


@pytest.fixture
def certified_alice() -> Student:
    alice = StudentFactory.create()
    PSetFactory.create(student=alice, clubs=0, hours=1501, status="A")
    Level.objects.create(name="Level Thirty Eight", threshold=38)
    return alice


@pytest.mark.django_db
def test_certify(otis, certified_alice) -> None:
    alice = certified_alice
    otis.login(alice)
    resp = otis.get_20x(
        "certify", alice.pk, alice.get_checksum(settings.CERT_HASH_KEY), follow=True
    )
    assert resp.context["hearts"] == 1501
    assert resp.context["level_number"] == 38
    assert resp.context["level_name"] == "Level Thirty Eight"


@pytest.mark.django_db
def test_certify_rejects_bad_checksum(otis, certified_alice) -> None:
    otis.login(certified_alice)
    otis.get_denied("certify", certified_alice.pk, "invalid")


@pytest.mark.django_db
def test_certify_of_other_student_denied(otis, certified_alice) -> None:
    otis.login(StudentFactory.create(semester=certified_alice.semester))
    otis.get_denied("certify", certified_alice.pk)
