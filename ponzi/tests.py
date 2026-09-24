import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from freezegun import freeze_time

from core.factories import UserFactory
from roster.factories import StudentFactory
from roster.models import Student
from rpg.factories import QuestCompleteFactory
from rpg.levelsys import get_level_info, get_student_rows

from .factories import PonziInvestmentFactory, PonziSchemeFactory
from .models import PonziInvestment, PonziScheme

UTC = datetime.UTC
START = datetime.datetime(2026, 1, 1, tzinfo=UTC)


def at(days: float) -> datetime.datetime:
    return START + datetime.timedelta(days=days)


def verified_user(spades: int = 100) -> User:
    group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(groups=(group,))
    if spades:
        QuestCompleteFactory.create(student__user=user, spades=spades)
    return user


@pytest.fixture
def scheme(db) -> PonziScheme:
    return PonziSchemeFactory.create(start_date=START)


@pytest.mark.django_db
def test_invest(otis, scheme: PonziScheme):
    alice = verified_user()
    otis.login(alice)
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 10})
        investment = PonziInvestment.objects.get(user=alice)
        assert investment.amount == 10
        assert investment.created_at == at(1)
        assert investment.tier == 0


@pytest.mark.django_db
@pytest.mark.parametrize("amount", [0, 11, 2.5, "lots"])
def test_invest_bad_amount(otis, scheme: PonziScheme, amount):
    otis.login(verified_user())
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": amount})
    assert not PonziInvestment.objects.exists()


@pytest.mark.django_db
def test_invest_cannot_go_into_debt(otis, scheme: PonziScheme):
    otis.login(verified_user(spades=7))
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 8})
        assert not PonziInvestment.objects.exists()
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 7})
    assert PonziInvestment.objects.get().amount == 7


@pytest.mark.django_db
def test_invest_once_per_day(otis, scheme: PonziScheme):
    otis.login(verified_user())
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
    with freeze_time(at(1.5)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
        assert PonziInvestment.objects.count() == 1
    with freeze_time(at(2.5)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
        assert PonziInvestment.objects.count() == 2


@pytest.mark.django_db
def test_invest_before_start(otis, scheme: PonziScheme):
    otis.login(verified_user())
    with freeze_time(at(-1)):
        resp = otis.get_ok("ponzi-list")
        assert list(resp.context["schemes"]) == [scheme]
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        assert resp.context["can_invest"] is False
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
    assert not PonziInvestment.objects.exists()


@pytest.mark.django_db
def test_any_verified_user_can_play(otis, scheme: PonziScheme):
    alice = verified_user(spades=0)
    otis.login(alice)
    with freeze_time(at(1)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
    assert resp.context["can_invest"] is True

    QuestCompleteFactory.create(
        student__user=alice, student__semester__active=False, spades=5
    )
    with freeze_time(at(1)):
        otis.post_30x("ponzi-invest", scheme.pk, data={"amount": 5})
    assert PonziInvestment.objects.get().user == alice


@pytest.mark.django_db
def test_cannot_touch_other_investments(otis, scheme: PonziScheme):
    with freeze_time(at(1)):
        investment = PonziInvestmentFactory.create(scheme=scheme)
    otis.login(verified_user())
    with freeze_time(at(20)):
        otis.post_not_found("ponzi-withdraw", investment.pk)
        otis.post_not_found("ponzi-upgrade", investment.pk)


@pytest.mark.django_db
def test_withdraw_tier_one(otis, scheme: PonziScheme):
    alice = verified_user()
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, amount=10)
        investment = PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=10)
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
    assert scheme.pool() == Decimal("9.33")

    with freeze_time(at(16)):
        otis.post_30x("ponzi-withdraw", investment.pk)
    investment.refresh_from_db()
    assert investment.payout == Decimal("10.67")
    assert investment.withdrawn_at == at(15)


@pytest.mark.django_db
def test_gestation_period_is_per_scheme(otis):
    scheme = PonziSchemeFactory.create(
        start_date=START, gestation_period=datetime.timedelta(days=3)
    )
    alice = verified_user()
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, amount=10)
        investment = PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=10)
    otis.login(alice)

    with freeze_time(at(2)):
        otis.post_30x("ponzi-withdraw", investment.pk)
        investment.refresh_from_db()
        assert investment.withdrawn_at is None

    with freeze_time(at(4)):
        otis.post_30x("ponzi-withdraw", investment.pk)
    investment.refresh_from_db()
    assert investment.withdrawn_at == at(4)


@pytest.mark.django_db
def test_upgrade_to_tier_three(otis, scheme: PonziScheme):
    alice = verified_user()
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, amount=10)
        investment = PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=10)
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
    assert investment.payout == Decimal("13.40")


@pytest.mark.django_db
def test_collapse(otis, scheme: PonziScheme):
    alice = verified_user()
    bob = verified_user()
    with freeze_time(at(0)):
        alice_inv = PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=10)
        bob_inv = PonziInvestmentFactory.create(scheme=scheme, user=bob, amount=10)

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
    otis.assert_testid(resp, "ponzi-all-bids")
    assert list(resp.context["all_investments"]) == [alice_inv, bob_inv]
    assert resp.context["summary"] == {
        "num_bids": 2,
        "num_players": 2,
        "total_bid": 20,
        "num_withdrawn": 1,
        "total_paid": Decimal("10.67"),
        "num_outstanding": 1,
        "total_outstanding": 10,
        "pool": Decimal("9.33"),
    }


@pytest.mark.django_db
def test_spades_accounting(scheme: PonziScheme):
    alice = verified_user(spades=30)
    student = Student.objects.get(user=alice)
    PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=10)
    PonziInvestmentFactory.create(
        scheme=scheme,
        user=alice,
        amount=10,
        payout=Decimal("11.40"),
        withdrawn_at=at(20),
    )
    expected = 30 - 10 - 10 + 11.4
    assert get_level_info(student)["meters"]["spades"].value == expected
    rows = get_student_rows(Student.objects.filter(pk=student.pk))
    assert rows[0]["spades"] == pytest.approx(expected)


@pytest.mark.django_db
def test_views_render(otis, scheme: PonziScheme):
    alice = verified_user()
    with freeze_time(at(0)):
        PonziInvestmentFactory.create(scheme=scheme, user=alice, amount=5)
    otis.login(alice)
    with freeze_time(at(0.5)):
        resp = otis.get_ok("ponzi-list")
        assert list(resp.context["schemes"]) == [scheme]
        assert resp.context["tier_returns"][2] == ("III", 34)
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        assert resp.context["num_investors"] == 1
        assert resp.context["spades_meter"].value == 95
        otis.assert_no_testid(resp, "ponzi-summary")
        assert "all_investments" not in resp.context
        assert "summary" not in resp.context
        otis.assert_no_testid(resp, "ponzi-all-bids")
        assert resp.context["can_invest"] is False
        otis.assert_no_testid(resp, "ponzi-invest-form")
    with freeze_time(at(1.5)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
        assert resp.context["can_invest"] is True
        otis.assert_testid(resp, "ponzi-invest-form")

    otis.login(UserFactory.create(is_staff=True))
    with freeze_time(at(8)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
    assert "summary" not in resp.context


@pytest.mark.django_db
def test_admin_sees_all_bids_before_collapse(otis, scheme: PonziScheme):
    with freeze_time(at(0)):
        first = PonziInvestmentFactory.create(scheme=scheme)
    with freeze_time(at(1)):
        second = PonziInvestmentFactory.create(scheme=scheme)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    with freeze_time(at(2)):
        resp = otis.get_ok("ponzi-scheme", scheme.pk)
    assert list(resp.context["all_investments"]) == [first, second]
    assert resp.context["summary"]["pool"] == 20
    otis.assert_testid(resp, "ponzi-summary")
    otis.assert_testid(resp, "ponzi-all-bids")


@pytest.mark.django_db
def test_unverified_users_are_denied(otis, scheme: PonziScheme):
    otis.login(StudentFactory.create(semester__active=True))
    otis.get_denied("ponzi-list")
    otis.get_denied("ponzi-scheme", scheme.pk)
    otis.post_denied("ponzi-invest", scheme.pk, data={"amount": 1})
    assert not PonziInvestment.objects.exists()
