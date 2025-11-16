import datetime

import pytest
from django.contrib.admin.sites import AdminSite
from django.http.request import HttpRequest
from django.test.client import RequestFactory
from freezegun import freeze_time

from core.factories import GroupFactory, SemesterFactory, UserFactory
from markets.admin import MarketAdmin
from markets.factories import GuessFactory, MarketFactory
from markets.models import Guess, Market

UTC = datetime.timezone.utc


@pytest.fixture
def market_model_data(db):
    MarketFactory.create(
        start_date=datetime.datetime(2000, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2000, 1, 3, tzinfo=UTC),
        slug="m-one",  # ended a long time ago
    )
    MarketFactory.create(
        start_date=datetime.datetime(2020, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2020, 1, 3, tzinfo=UTC),
        slug="m-two",  # active
    )
    MarketFactory.create(
        start_date=datetime.datetime(2050, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2050, 1, 3, tzinfo=UTC),
        slug="m-three",  # future
    )


@pytest.mark.django_db
def test_managers(market_model_data):
    with freeze_time("2020-01-02", tz_offset=0):
        assert Market.started.count() == 2
        assert Market.active.count() == 1
        assert Market.active.get().slug == "m-two"


@pytest.mark.django_db
def test_urls(market_model_data):
    with freeze_time("2020-01-02", tz_offset=0):
        m1 = Market.objects.get(slug="m-one")
        m2 = Market.objects.get(slug="m-two")
        m3 = Market.objects.get(slug="m-three")
        g1 = GuessFactory.create(market=m1)
        g2 = GuessFactory.create(market=m2)
        g3 = GuessFactory.create(market=m3)

        assert g1.get_absolute_url() == m1.get_absolute_url()
        assert g3.get_absolute_url() == m3.get_absolute_url()
        assert g2.get_absolute_url() != m2.get_absolute_url()


@pytest.mark.django_db
def test_list(otis, market_model_data):
    with freeze_time("2020-01-02", tz_offset=0):
        otis.login(UserFactory.create())
        response = otis.get("market-list")
        otis.assert_has(response, "m-one")
        otis.assert_has(response, "m-two")
        otis.assert_not_has(response, "m-three")


@pytest.mark.django_db
def test_model_str(market_model_data):
    str(MarketFactory.create())
    str(GuessFactory.create())


@pytest.mark.django_db
def test_admin_action(market_model_data):
    site = AdminSite()
    admin = MarketAdmin(Market, site)
    request: HttpRequest = RequestFactory().get("/")
    qs = Market.objects.filter(slug="m-three")
    admin.postpone_market(request, qs)
    assert qs.get().start_date == datetime.datetime(2050, 1, 8, tzinfo=UTC)
    assert qs.get().end_date == datetime.datetime(2050, 1, 10, tzinfo=UTC)
    admin.hasten_market(request, qs)
    assert qs.get().start_date == datetime.datetime(2050, 1, 1, tzinfo=UTC)
    assert qs.get().end_date == datetime.datetime(2050, 1, 3, tzinfo=UTC)


@pytest.fixture
def market_data(db):
    MarketFactory(
        start_date=datetime.datetime(2050, 5, 1, 0, 0, 0, tzinfo=UTC),
        end_date=datetime.datetime(2050, 9, 30, 23, 59, 59, tzinfo=UTC),
        weight=2,
        alpha=2,
        slug="guess-my-ssn",
        int_guesses_only=True,
    )
    verified_group = GroupFactory(name="Verified")
    UserFactory(username="alice", groups=(verified_group,))


@pytest.mark.django_db
def test_has_started(market_data):
    market = Market.objects.get(slug="guess-my-ssn")
    with freeze_time("2050-01-01", tz_offset=0):
        assert not market.has_started
    with freeze_time("2050-07-01", tz_offset=0):
        assert market.has_started
    with freeze_time("2050-11-01", tz_offset=0):
        assert market.has_started


@pytest.mark.django_db
def test_has_ended(market_data):
    market = Market.objects.get(slug="guess-my-ssn")
    with freeze_time("2050-01-01", tz_offset=0):
        assert not market.has_ended
    with freeze_time("2050-07-01", tz_offset=0):
        assert not market.has_ended
    with freeze_time("2050-11-01", tz_offset=0):
        assert market.has_ended


@pytest.mark.django_db
def test_results_perms(otis, market_data):
    with freeze_time("2050-01-01", tz_offset=0):
        otis.login("alice")
        otis.get_40x("market-results", "guess-my-ssn")
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")
        otis.get_redirects(
            otis.url("market-guess", "guess-my-ssn"),
            "market-results",
            "guess-my-ssn",
        )
    with freeze_time("2050-11-01", tz_offset=0):
        otis.login("alice")
        otis.get_20x("market-results", "guess-my-ssn")


@pytest.mark.django_db
def test_guess_perms(otis, market_data):
    with freeze_time("2050-01-01", tz_offset=0):
        otis.login("alice")
        otis.get_40x("market-guess", "guess-my-ssn")
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")
        resp = otis.get_20x("market-guess", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
    with freeze_time("2050-11-01", tz_offset=0):
        otis.login("alice")
        otis.get_redirects(
            otis.url("market-results", "guess-my-ssn"),
            "market-guess",
            "guess-my-ssn",
        )


@pytest.mark.django_db
def test_guess_form_gated_on_verified(otis, market_data):
    with freeze_time("2050-07-01", tz_offset=0):
        market = Market.objects.get(slug="guess-my-ssn")
        market.answer = 42
        market.save()
        UserFactory.create(username="eve")
        otis.login("eve")
        otis.post_40x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)


@pytest.mark.django_db
def test_guess_form_with_answer(otis, market_data):
    with freeze_time("2050-07-01", tz_offset=0):
        market = Market.objects.get(slug="guess-my-ssn")
        market.answer = 42
        market.save()

        otis.login("alice")

        # Guess a non-integer, shouldn't work
        resp = otis.get_20x("market-guess", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
        resp = otis.post_20x(
            "market-guess", "guess-my-ssn", data={"value": 13.37}, follow=True
        )
        assert "This market only allows integer guesses." in resp.content.decode()

        # Guess an integer, should save
        resp = otis.get_20x("market-guess", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)

        # Forbid more guesses
        otis.get_30x("market-guess", "guess-my-ssn")  # redirects to DetailView
        resp = otis.post_20x(
            "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
        )
        assert "You already submitted" in resp.content.decode()

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 100
        assert guess.score == pytest.approx(round((42 / 100) ** 2 * 2, ndigits=2))


@pytest.mark.django_db
def test_guess_form_without_answer(otis, market_data):
    with freeze_time("2050-07-01", tz_offset=0):
        market = Market.objects.get(slug="guess-my-ssn")
        otis.login("alice")
        resp = otis.get_20x("market-guess", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)
        otis.get_30x("market-guess", "guess-my-ssn")  # redirects to DetailView
        resp = otis.post_20x(
            "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
        )
        assert "You already submitted" in resp.content.decode()

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 100
        assert guess.score is None

        market.answer = 42
        market.save()
        otis.post_40x("market-recompute", "guess-my-ssn")

        UserFactory.create(username="admin", is_staff=True, is_superuser=True)
        otis.login("admin")
        otis.post_redirects(
            otis.url("market-results", "guess-my-ssn"),
            "market-recompute",
            "guess-my-ssn",
        )

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 100
        assert guess.score == pytest.approx(round((42 / 100) ** 2 * 2, ndigits=2))


@pytest.mark.django_db
def test_guess_form_without_alpha(otis, market_data):
    with freeze_time("2050-07-01", tz_offset=0):
        market = Market.objects.get(slug="guess-my-ssn")
        market.alpha = None
        market.save()
        otis.login("alice")
        resp = otis.get_20x("market-guess", "guess-my-ssn")
        otis.assert_not_has(resp, "market main page")  # because it's a special market
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)

        otis.get_30x("market-guess", "guess-my-ssn")  # redirects to DetailView
        resp = otis.post_20x(
            "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
        )
        assert "You already submitted" in resp.content.decode()

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 100
        assert guess.score is None

        market.answer = 42
        market.alpha = 3
        market.save()
        otis.post_40x("market-recompute", "guess-my-ssn")

        UserFactory.create(username="admin", is_staff=True, is_superuser=True)
        otis.login("admin")
        otis.post_redirects(
            otis.url("market-results", "guess-my-ssn"),
            "market-recompute",
            "guess-my-ssn",
        )

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 100
        assert guess.score == pytest.approx(round((42 / 100) ** 3 * 2, ndigits=2))


@pytest.mark.django_db
def test_spades_view(otis, market_data):
    market = Market.objects.get(slug="guess-my-ssn")
    market.answer = 42
    market.save()
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)
        resp = otis.get_20x("market-spades")
        otis.assert_has(resp, "You have not completed")
    with freeze_time("2050-11-01", tz_offset=0):
        otis.login("alice")
        resp = otis.get_20x("market-spades")
        assert resp.context["avg"] == pytest.approx(
            round((42 / 100) ** 2 * 2, ndigits=2)
        )


@pytest.mark.django_db
def test_update_guess_perms(otis, market_data):
    """Test that update guess view respects permissions"""
    with freeze_time("2050-01-01", tz_offset=0):
        otis.login("alice")
        otis.get_40x("market-guess-update", "guess-my-ssn")
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")
        # Create a guess first
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 13}, follow=True)
        guess = Guess.objects.get(market__slug="guess-my-ssn", user__username="alice")
        assert guess.value == 13
        # Now we can update it
        resp = otis.get_20x("market-guess-update", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
        otis.post_20x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 23},
            follow=True,
        )
        guess.refresh_from_db()

        assert guess.value == 23

    with freeze_time("2050-11-01", tz_offset=0):
        otis.login("alice")
        otis.get_40x(
            "market-guess-update",
            "guess-my-ssn",
        )
        otis.post_40x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 10500000},
            follow=True,
        )
        guess.refresh_from_db()
        assert guess.value == 23


@pytest.mark.django_db
def test_update_guess_form_with_answer(otis, market_data):
    """Test updating a guess with integer validation and score recalculation"""
    with freeze_time("2050-07-01", tz_offset=0):
        market = Market.objects.get(slug="guess-my-ssn")
        market.answer = 42
        market.save()

        otis.login("alice")

        # Create initial guess
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 13}, follow=True)

        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 13
        assert guess.score == pytest.approx(round((13 / 42) ** 2 * 2, ndigits=2))

        # Try to update with a non-integer (should fail)
        resp = otis.get_20x("market-guess-update", "guess-my-ssn")
        otis.assert_has(resp, "market main page")
        resp = otis.post_20x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 13.37},
            follow=True,
        )
        assert "This market only allows integer guesses." in resp.content.decode()

        # Update with a valid integer
        resp = otis.post_20x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 23},
            follow=True,
        )
        assert "You updated your guess to 23" in resp.content.decode()

        # Check that the guess was updated
        guess = Guess.objects.get(user__username="alice")
        assert guess.value == 23
        assert guess.score == pytest.approx(round((23 / 42) ** 2 * 2, ndigits=2))


@pytest.mark.django_db
def test_update_guess_changes_public_flag(otis, market_data):
    """Test that updating a guess can change the public flag"""
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")

        # Create initial guess with public=False (default)
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 100}, follow=True)

        guess = Guess.objects.get(user__username="alice")
        assert guess.public is False

        # Update to make it public
        otis.post_20x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 13, "public": True},
            follow=True,
        )

        guess = Guess.objects.get(user__username="alice")
        assert guess.public is True

        # Update to make it private again
        otis.post_20x(
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 13, "public": False},
            follow=True,
        )

        guess = Guess.objects.get(user__username="alice")
        assert guess.public is False


@pytest.mark.django_db
def test_update_guess_redirects_to_pending(otis, market_data):
    """Test that successful update redirects to pending view"""
    with freeze_time("2050-07-01", tz_offset=0):
        otis.login("alice")

        # Create initial guess
        otis.post_20x("market-guess", "guess-my-ssn", data={"value": 13}, follow=True)

        # Update and check redirect
        otis.post_redirects(
            otis.url("market-pending", "guess-my-ssn"),
            "market-guess-update",
            "guess-my-ssn",
            data={"value": 23},
        )


@pytest.fixture
def create_market_data(db):
    SemesterFactory.create(active=True)


@pytest.mark.django_db
def test_create_market(otis, create_market_data):
    admin = UserFactory.create(is_staff=True, is_superuser=True)

    with freeze_time("2050-01-01", tz_offset=0):
        otis.login(admin)

        otis.post_20x(
            "market-new",
            data={
                "slug": "market1",
                "title": "Market 1",
                "prompt_plain": "Prompt for market 1",
            },
            follow=True,
        )
        market1 = Market.objects.get(slug="market1")
        assert market1.start_date.year == 2050
        assert market1.start_date.month == 1
        assert market1.start_date.day == 8
        assert market1.end_date.year == 2050
        assert market1.end_date.month == 1
        assert market1.end_date.day == 11

        otis.post_20x(
            "market-new",
            data={
                "slug": "market2",
                "title": "Market 2",
                "prompt_plain": "Prompt for market 2",
            },
            follow=True,
        )
        market2 = Market.objects.get(slug="market2")
        assert market2.start_date.year == 2050
        assert market2.start_date.month == 1
        assert market2.start_date.day == 15
        assert market2.end_date.year == 2050
        assert market2.end_date.month == 1
        assert market2.end_date.day == 18

    with freeze_time("2050-01-19", tz_offset=0):
        otis.login(admin)
        otis.post_20x(
            "market-new",
            data={
                "slug": "market3",
                "title": "Market 3",
                "prompt_plain": "Prompt for market 3",
            },
            follow=True,
        )
        market3 = Market.objects.get(slug="market3")
        assert market3.start_date.year == 2050
        assert market3.start_date.month == 1
        assert market3.start_date.day == 22
        assert market3.end_date.year == 2050
        assert market3.end_date.month == 1
        assert market3.end_date.day == 25

    with freeze_time("2050-03-01", tz_offset=0):
        otis.login(admin)
        otis.post_20x(
            "market-new",
            data={
                "slug": "market4",
                "title": "Market 4",
                "prompt_plain": "Prompt for market 4",
            },
            follow=True,
        )
        market4 = Market.objects.get(slug="market4")
        assert market4.start_date.year == 2050
        assert market4.start_date.month == 3
        assert market4.start_date.day == 1
        assert market4.end_date.year == 2050
        assert market4.end_date.month == 3
        assert market4.end_date.day == 4
