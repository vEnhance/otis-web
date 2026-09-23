import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from freezegun import freeze_time

from core.factories import UserFactory
from roster.factories import StudentFactory
from roster.models import Student, StudentStanding
from rpg.factories import QuestCompleteFactory
from rpg.levelsys import get_level_info, get_student_rows

from .factories import PonziInvestmentFactory, PonziSchemeFactory
from .models import PonziInvestment, PonziScheme

UTC = datetime.UTC
START = datetime.datetime(2026, 1, 1, tzinfo=UTC)


def at(days: float) -> datetime.datetime:
    return START + datetime.timedelta(days=days)


def verified_student(scheme: PonziScheme, spades: int = 100, **kwargs) -> Student:
    group, _ = Group.objects.get_or_create(name="Verified")
    student = StudentFactory.create(
        semester=scheme.semester, user__groups=(group,), **kwargs
    )
    if spades:
        QuestCompleteFactory.create(student=student, spades=spades)
    return student


@pytest.fixture
def scheme(db) -> PonziScheme:
    return PonziSchemeFactory.create(start_date=START)


@pytest.mark.django_db
def test_invest(otis, scheme: PonziScheme):
    alice = verified_student(scheme)
    otis.login(alice)
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 15})
        investment = PonziInvestment.objects.get(student=alice)
        assert investment.amount == 15
        assert investment.created_at == at(1)
        assert investment.tier == 0


@pytest.mark.django_db
@pytest.mark.parametrize("amount", [0, 21, 2.5, "lots"])
def test_invest_bad_amount(otis, scheme: PonziScheme, amount):
    otis.login(verified_student(scheme))
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": amount})
    assert not PonziInvestment.objects.exists()


@pytest.mark.django_db
def test_invest_cannot_go_into_debt(otis, scheme: PonziScheme):
    otis.login(verified_student(scheme, spades=7))
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 8})
        assert not PonziInvestment.objects.exists()
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 7})
    assert PonziInvestment.objects.get().amount == 7


@pytest.mark.django_db
def test_invest_once_per_week(otis, scheme: PonziScheme):
    otis.login(verified_student(scheme))
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
    with freeze_time(at(7.5)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
        assert PonziInvestment.objects.count() == 1
    with freeze_time(at(8.5)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
        assert PonziInvestment.objects.count() == 2


@pytest.mark.django_db
def test_invest_before_start(otis, scheme: PonziScheme):
    otis.login(verified_student(scheme))
    with freeze_time(at(-1)):
        otis.get_denied("ponzi-scheme", scheme.pk)
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
    assert not PonziInvestment.objects.exists()


@pytest.mark.django_db
def test_only_active_students_play(otis, scheme: PonziScheme):
    other_semester = PonziSchemeFactory.create(start_date=START)
    otis.login(verified_student(other_semester))
    with freeze_time(at(1)):
        otis.post_denied("ponzi-invest", scheme.pk, data={"amount": 5})

    otis.login(verified_student(scheme, standing=StudentStanding.DROPPED))
    with freeze_time(at(1)):
        otis.post_denied("ponzi-invest", scheme.pk, data={"amount": 5})
    assert not PonziInvestment.objects.exists()


@pytest.mark.django_db
def test_cannot_touch_other_investments(otis, scheme: PonziScheme):
    with freeze_time(at(1)):
        investment = PonziInvestmentFactory.create(scheme=scheme)
    otis.login(verified_student(scheme))
    with freeze_time(at(20)):
        otis.post_not_found("ponzi-withdraw", investment.pk)
        otis.post_not_found("ponzi-upgrade", investment.pk)


@pytest.mark.django_db
def test_withdraw_tier_one(otis, scheme: PonziScheme):
    alice = verified_student(scheme)
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, amount=20)
        investment = PonziInvestmentFactory.create(
            scheme=scheme, student=alice, amount=10
        )
    otis.login(alice)

    with freeze_time(at(13)):
        otis.post_30x("ponzi-withdraw", investment.pk)
        investment.refresh_from_db()
        assert investment.withdrawn_at is None

    with freeze_time(at(15)):
        otis.post_30x("ponzi-withdraw", investment.pk)
    investment.refresh_from_db()
    assert investment.payout == Decimal("10.67")
    assert investment.withdrawn_at == at(15)
    assert scheme.pool() == Decimal("19.33")

    with freeze_time(at(16)):
        otis.post_30x("ponzi-withdraw", investment.pk)
    investment.refresh_from_db()
    assert investment.payout == Decimal("10.67")
    assert investment.withdrawn_at == at(15)


@pytest.mark.django_db
def test_upgrade_to_tier_three(otis, scheme: PonziScheme):
    alice = verified_student(scheme)
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, amount=20)
        investment = PonziInvestmentFactory.create(
            scheme=scheme, student=alice, amount=20
        )
    otis.login(alice)

    with freeze_time(at(10)):
        otis.post_30x("ponzi-upgrade", investment.pk)
        investment.refresh_from_db()
        assert investment.target_tier == 1

    with freeze_time(at(15)):
        otis.post_30x("ponzi-upgrade", investment.pk)
        investment.refresh_from_db()
        assert investment.target_tier == 2
        assert investment.upgraded_at == at(15)
        assert investment.tier == 1
        otis.post_30x("ponzi-withdraw", investment.pk)
        investment.refresh_from_db()
        assert investment.withdrawn_at is None

    with freeze_time(at(30)):
        assert investment.tier == 2
        otis.post_30x("ponzi-upgrade", investment.pk)
    with freeze_time(at(45)):
        otis.post_30x("ponzi-upgrade", investment.pk)
        investment.refresh_from_db()
        assert investment.target_tier == 3
        assert investment.tier == 3
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        otis.assert_testid(resp, "ponzi-withdraw")
        otis.assert_no_testid(resp, "ponzi-upgrade")
        otis.post_30x("ponzi-withdraw", investment.pk)
    investment.refresh_from_db()
    assert investment.payout == Decimal("26.80")


@pytest.mark.django_db
def test_collapse(otis, scheme: PonziScheme):
    alice = verified_student(scheme)
    bob = verified_student(scheme)
    with freeze_time(at(0)):
        alice_inv = PonziInvestmentFactory.create(
            scheme=scheme, student=alice, amount=10
        )
        bob_inv = PonziInvestmentFactory.create(scheme=scheme, student=bob, amount=10)

    with freeze_time(at(15)):
        otis.login(alice)
        otis.post_30x("ponzi-withdraw", alice_inv.pk)
        otis.login(bob)
        otis.post_30x("ponzi-withdraw", bob_inv.pk)

    scheme.refresh_from_db()
    bob_inv.refresh_from_db()
    assert scheme.collapsed_at == at(15)
    assert scheme.collapsed_by == bob
    assert bob_inv.payout is None
    assert bob_inv.withdrawn_at is None

    with freeze_time(at(40)):
        otis.login(bob)
        otis.post_30x("ponzi-withdraw", bob_inv.pk)
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 1})
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
    bob_inv.refresh_from_db()
    assert bob_inv.payout is None
    assert PonziInvestment.objects.count() == 2
    otis.assert_testid(resp, "ponzi-collapsed")
    otis.assert_no_testid(resp, "ponzi-invest-form")


@pytest.mark.django_db
def test_spades_accounting(scheme: PonziScheme):
    alice = verified_student(scheme, spades=30)
    PonziInvestmentFactory.create(scheme=scheme, student=alice, amount=20)
    PonziInvestmentFactory.create(
        scheme=scheme,
        student=alice,
        amount=10,
        payout=Decimal("11.40"),
        withdrawn_at=at(20),
    )
    expected = 30 - 20 - 10 + 11.4
    assert get_level_info(alice)["meters"]["spades"].value == expected
    rows = get_student_rows(Student.objects.filter(pk=alice.pk))
    assert rows[0]["spades"] == pytest.approx(expected)


@pytest.mark.django_db
def test_views_render(otis, scheme: PonziScheme):
    alice = verified_student(scheme)
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, student=alice, amount=5)
    otis.login(alice)
    with freeze_time(at(3)):
        resp = otis.get_ok("ponzi-list")
        assert list(resp.context["schemes"]) == [scheme]
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        assert "pool" not in resp.context
        assert "num_investors" not in resp.context
        otis.assert_no_testid(resp, "ponzi-pool")
        assert resp.context["can_invest"] is False
        otis.assert_no_testid(resp, "ponzi-invest-form")
    with freeze_time(at(8)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        assert resp.context["can_invest"] is True
        otis.assert_testid(resp, "ponzi-invest-form")

    otis.login(UserFactory.create(is_staff=True))
    with freeze_time(at(8)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
    assert resp.context["pool"] == 5
    assert resp.context["num_investors"] == 1
    otis.assert_testid(resp, "ponzi-pool")
