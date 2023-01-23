from core.factories import UserFactory, GroupFactory
from django.utils import timezone
from freezegun import freeze_time
from evans_django_tools.testsuite import EvanTestCase

from markets.factories import GuessFactory, MarketFactory
from markets.models import Guess, Market

UTC = timezone.utc


class MarketModelTests(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        MarketFactory.create(
            start_date=timezone.datetime(2000, 1, 1, tzinfo=UTC),
            end_date=timezone.datetime(2000, 1, 3, tzinfo=UTC),
            slug="m-one",  # ended a long time ago
        )
        MarketFactory.create(
            start_date=timezone.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=timezone.datetime(2020, 1, 3, tzinfo=UTC),
            slug="m-two",  # active
        )
        MarketFactory.create(
            start_date=timezone.datetime(2050, 1, 1, tzinfo=UTC),
            end_date=timezone.datetime(2050, 1, 3, tzinfo=UTC),
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


class MarketTests(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        MarketFactory(
            start_date=timezone.datetime(2050, 5, 1, 0, 0, 0, tzinfo=UTC),
            end_date=timezone.datetime(2050, 9, 30, 23, 59, 59, tzinfo=UTC),
            weight=2,
            alpha=2,
            slug="guess-my-ssn",
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
            resp = self.assertGet20X("market-guess", "guess-my-ssn")
            self.assertHas(resp, "market main page")
            self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 100}, follow=True
            )

            resp = self.assertGet20X("market-guess", "guess-my-ssn", follow=True)
            self.assertHas(resp, "You already submitted")

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

            resp = self.assertGet20X("market-guess", "guess-my-ssn", follow=True)
            self.assertHas(resp, "You already submitted")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertEqual(guess.score, None)

            market.answer = 42
            market.save()
            self.assertPostBecomesStaffRedirect(
                "market-recompute", "guess-my-ssn", follow=True
            )

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

            resp = self.assertGet20X("market-guess", "guess-my-ssn", follow=True)
            self.assertHas(resp, "You already submitted")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 100)
            self.assertEqual(guess.score, None)

            market.answer = 42
            market.alpha = 3
            market.save()
            self.assertPostBecomesStaffRedirect(
                "market-recompute", "guess-my-ssn", follow=True
            )

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
