import datetime

from django.contrib.admin.sites import AdminSite
from django.http.request import HttpRequest
from django.test.client import RequestFactory
from freezegun import freeze_time

from core.factories import GroupFactory, SemesterFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase
from markets.admin import MarketAdmin
from markets.factories import GuessFactory, MarketFactory
from markets.models import Guess, Market

UTC = datetime.timezone.utc


class MarketModelTests(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_managers(self):
        with freeze_time("2020-01-02", tz_offset=0):
            self.assertEqual(Market.started.count(), 2)
            self.assertEqual(Market.active.count(), 1)
            self.assertEqual(Market.active.get().slug, "m-two")

    def test_urls(self):
        with freeze_time("2020-01-02", tz_offset=0):
            m1 = Market.objects.get(slug="m-one")
            m2 = Market.objects.get(slug="m-two")
            m3 = Market.objects.get(slug="m-three")
            g1 = GuessFactory.create(market=m1)
            g2 = GuessFactory.create(market=m2)
            g3 = GuessFactory.create(market=m3)

            self.assertEqual(g1.get_absolute_url(), m1.get_absolute_url())
            self.assertEqual(g3.get_absolute_url(), m3.get_absolute_url())
            self.assertNotEqual(g2.get_absolute_url(), m2.get_absolute_url())

    def test_list(self):
        with freeze_time("2020-01-02", tz_offset=0):
            self.login(UserFactory.create())
            response = self.get("market-list")
            self.assertHas(response, "m-one")
            self.assertHas(response, "m-two")
            self.assertNotHas(response, "m-three")

    def test_model_str(self):
        str(MarketFactory.create())
        str(GuessFactory.create())

    def test_admin_action(self):
        site = AdminSite()
        admin = MarketAdmin(Market, site)
        request: HttpRequest = RequestFactory().get("/")
        qs = Market.objects.filter(slug="m-three")
        admin.postpone_market(request, qs)
        self.assertEqual(
            qs.get().start_date,
            datetime.datetime(2050, 1, 8, tzinfo=UTC),
        )
        self.assertEqual(
            qs.get().end_date,
            datetime.datetime(2050, 1, 10, tzinfo=UTC),
        )
        admin.hasten_market(request, qs)
        self.assertEqual(
            qs.get().start_date,
            datetime.datetime(2050, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(
            qs.get().end_date,
            datetime.datetime(2050, 1, 3, tzinfo=UTC),
        )


class MarketTests(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_has_started(self):
        market = Market.objects.get(slug="guess-my-ssn")
        with freeze_time("2050-01-01", tz_offset=0):
            self.assertFalse(market.has_started)
        with freeze_time("2050-07-01", tz_offset=0):
            self.assertTrue(market.has_started)
        with freeze_time("2050-11-01", tz_offset=0):
            self.assertTrue(market.has_started)

    def test_has_ended(self):
        market = Market.objects.get(slug="guess-my-ssn")
        with freeze_time("2050-01-01", tz_offset=0):
            self.assertFalse(market.has_ended)
        with freeze_time("2050-07-01", tz_offset=0):
            self.assertFalse(market.has_ended)
        with freeze_time("2050-11-01", tz_offset=0):
            self.assertTrue(market.has_ended)

    def test_results_perms(self):
        with freeze_time("2050-01-01", tz_offset=0):
            self.login("alice")
            self.assertGet40X("market-results", "guess-my-ssn")
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")
            self.assertGetRedirects(
                self.url("market-guess", "guess-my-ssn"),
                "market-results",
                "guess-my-ssn",
            )
        with freeze_time("2050-11-01", tz_offset=0):
            self.login("alice")
            self.assertGet20X("market-results", "guess-my-ssn")

    def test_guess_perms(self):
        with freeze_time("2050-01-01", tz_offset=0):
            self.login("alice")
            self.assertGet40X("market-guess", "guess-my-ssn")
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertHas(resp, "market main page")
        with freeze_time("2050-11-01", tz_offset=0):
            self.login("alice")
            self.assertGetRedirects(
                self.url("market-results", "guess-my-ssn"),
                "market-guess",
                "guess-my-ssn",
            )

    def test_guess_form_gated_on_verified(self):
        with freeze_time("2050-07-01", tz_offset=0):
            market = Market.objects.get(slug="guess-my-ssn")
            market.answer = 42
            market.save()
            UserFactory.create(username="eve")
            self.login("eve")
            self.assertPost40X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )

    def test_guess_form_with_answer(self):
        with freeze_time("2050-07-01", tz_offset=0):
            market = Market.objects.get(slug="guess-my-ssn")
            market.answer = 42
            market.save()

            self.login("alice")

            # Guess a non-integer, shouldn't work
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 13.37}, follow=True
            )
            self.assertContains(resp, "This market only allows integer guesses.")

            # Guess an integer, should save
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )

            # Forbid more guesses
            self.assertGet30X("market-guess", "guess-my-ssn")  # redirects to DetailView
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
            )
            self.assertContains(resp, "You already submitted")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertAlmostEqual(guess.score, round((42 / 100) ** 2 * 2, ndigits=2))

    def test_guess_form_without_answer(self):
        with freeze_time("2050-07-01", tz_offset=0):
            market = Market.objects.get(slug="guess-my-ssn")
            self.login("alice")
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )
            self.assertGet30X("market-guess", "guess-my-ssn")  # redirects to DetailView
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
            )
            self.assertContains(resp, "You already submitted")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertEqual(guess.score, None)

            market.answer = 42
            market.save()
            self.assertPost40X("market-recompute", "guess-my-ssn")

            UserFactory.create(username="admin", is_staff=True, is_superuser=True)
            self.login("admin")
            self.assertPostRedirects(
                self.url("market-results", "guess-my-ssn"),
                "market-recompute",
                "guess-my-ssn",
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertAlmostEqual(guess.score, round((42 / 100) ** 2 * 2, ndigits=2))

    def test_guess_form_without_alpha(self):
        with freeze_time("2050-07-01", tz_offset=0):
            market = Market.objects.get(slug="guess-my-ssn")
            market.alpha = None
            market.save()
            self.login("alice")
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertNotHas(resp, "market main page")  # because it's a special market
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )

            self.assertGet30X("market-guess", "guess-my-ssn")  # redirects to DetailView
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
            )
            self.assertContains(resp, "You already submitted")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertEqual(guess.score, None)

            market.answer = 42
            market.alpha = 3
            market.save()
            self.assertPost40X("market-recompute", "guess-my-ssn")

            UserFactory.create(username="admin", is_staff=True, is_superuser=True)
            self.login("admin")
            self.assertPostRedirects(
                self.url("market-results", "guess-my-ssn"),
                "market-recompute",
                "guess-my-ssn",
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertAlmostEqual(guess.score, round((42 / 100) ** 3 * 2, ndigits=2))

    def test_spades_view(self):
        market = Market.objects.get(slug="guess-my-ssn")
        market.answer = 42
        market.save()
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )
            resp = self.assertGet20X("market-spades")
            self.assertHas(resp, "You have not completed")
        with freeze_time("2050-11-01", tz_offset=0):
            self.login("alice")
            resp = self.assertGet20X("market-spades")
            self.assertAlmostEqual(
                resp.context["avg"], round((42 / 100) ** 2 * 2, ndigits=2)
            )

    def test_update_guess_perms(self):
        """Test that update guess view respects permissions"""
        with freeze_time("2050-01-01", tz_offset=0):
            self.login("alice")
            self.assertGet40X("market-guess-update", "guess-my-ssn")
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")
            # Create a guess first
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 13}, follow=True
            )
            guess = Guess.objects.get(
                market__slug="guess-my-ssn", user__username="alice"
            )
            self.assertEqual(guess.value, 13)
            # Now we can update it
            resp = self.assertGet20X("market-guess-update", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            self.assertPost20X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 23},
                follow=True,
            )
            guess.refresh_from_db()

            self.assertEqual(guess.value, 23)

        with freeze_time("2050-11-01", tz_offset=0):
            self.login("alice")
            self.assertGet40X(
                "market-guess-update",
                "guess-my-ssn",
            )
            self.assertPost40X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 10500000},
                follow=True,
            )
            guess.refresh_from_db()
            self.assertEqual(guess.value, 23)

    def test_update_guess_form_with_answer(self):
        """Test updating a guess with integer validation and score recalculation"""
        with freeze_time("2050-07-01", tz_offset=0):
            market = Market.objects.get(slug="guess-my-ssn")
            market.answer = 42
            market.save()

            self.login("alice")

            # Create initial guess
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 13}, follow=True
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 13)
            self.assertAlmostEqual(guess.score, round((13 / 42) ** 2 * 2, ndigits=2))

            # Try to update with a non-integer (should fail)
            resp = self.assertGet20X("market-guess-update", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            resp = self.assertPost20X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 13.37},
                follow=True,
            )
            self.assertContains(resp, "This market only allows integer guesses.")

            # Update with a valid integer
            resp = self.assertPost20X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 23},
                follow=True,
            )
            self.assertContains(resp, "You updated your guess to 23")

            # Check that the guess was updated
            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 23)
            self.assertAlmostEqual(guess.score, round((23 / 42) ** 2 * 2, ndigits=2))

    def test_update_guess_changes_public_flag(self):
        """Test that updating a guess can change the public flag"""
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")

            # Create initial guess with public=False (default)
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.public, False)

            # Update to make it public
            self.assertPost20X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 13, "public": True},
                follow=True,
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.public, True)

            # Update to make it private again
            self.assertPost20X(
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 13, "public": False},
                follow=True,
            )

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.public, False)

    def test_update_guess_redirects_to_pending(self):
        """Test that successful update redirects to pending view"""
        with freeze_time("2050-07-01", tz_offset=0):
            self.login("alice")

            # Create initial guess
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 13}, follow=True
            )

            # Update and check redirect
            self.assertPostRedirects(
                self.url("market-pending", "guess-my-ssn"),
                "market-guess-update",
                "guess-my-ssn",
                data={"value": 23},
            )


class CreateMarketTests(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        SemesterFactory.create(active=True)

    def test_create_market(self):
        admin = UserFactory.create(is_staff=True, is_superuser=True)

        with freeze_time("2050-01-01", tz_offset=0):
            self.login(admin)

            self.assertPost20X(
                "market-new",
                data={
                    "slug": "market1",
                    "title": "Market 1",
                    "prompt_plain": "Prompt for market 1",
                },
                follow=True,
            )
            market1 = Market.objects.get(slug="market1")
            self.assertEqual(market1.start_date.year, 2050)
            self.assertEqual(market1.start_date.month, 1)
            self.assertEqual(market1.start_date.day, 8)
            self.assertEqual(market1.end_date.year, 2050)
            self.assertEqual(market1.end_date.month, 1)
            self.assertEqual(market1.end_date.day, 11)

            self.assertPost20X(
                "market-new",
                data={
                    "slug": "market2",
                    "title": "Market 2",
                    "prompt_plain": "Prompt for market 2",
                },
                follow=True,
            )
            market2 = Market.objects.get(slug="market2")
            self.assertEqual(market2.start_date.year, 2050)
            self.assertEqual(market2.start_date.month, 1)
            self.assertEqual(market2.start_date.day, 15)
            self.assertEqual(market2.end_date.year, 2050)
            self.assertEqual(market2.end_date.month, 1)
            self.assertEqual(market2.end_date.day, 18)

        with freeze_time("2050-01-19", tz_offset=0):
            self.login(admin)
            self.assertPost20X(
                "market-new",
                data={
                    "slug": "market3",
                    "title": "Market 3",
                    "prompt_plain": "Prompt for market 3",
                },
                follow=True,
            )
            market3 = Market.objects.get(slug="market3")
            self.assertEqual(market3.start_date.year, 2050)
            self.assertEqual(market3.start_date.month, 1)
            self.assertEqual(market3.start_date.day, 22)
            self.assertEqual(market3.end_date.year, 2050)
            self.assertEqual(market3.end_date.month, 1)
            self.assertEqual(market3.end_date.day, 25)

        with freeze_time("2050-03-01", tz_offset=0):
            self.login(admin)
            self.assertPost20X(
                "market-new",
                data={
                    "slug": "market4",
                    "title": "Market 4",
                    "prompt_plain": "Prompt for market 4",
                },
                follow=True,
            )
            market4 = Market.objects.get(slug="market4")
            self.assertEqual(market4.start_date.year, 2050)
            self.assertEqual(market4.start_date.month, 3)
            self.assertEqual(market4.start_date.day, 1)
            self.assertEqual(market4.end_date.year, 2050)
            self.assertEqual(market4.end_date.month, 3)
            self.assertEqual(market4.end_date.day, 4)
