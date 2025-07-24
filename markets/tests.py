import datetime

from django.contrib.admin.sites import AdminSite
from django.http.request import HttpRequest
from django.test.client import RequestFactory
from freezegun import freeze_time
from django.urls import reverse

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

            # Market always goes to results
            self.assertEqual(m1.get_absolute_url(), reverse("market-results", args=(m1.slug,)))
            self.assertEqual(m2.get_absolute_url(), reverse("market-results", args=(m2.slug,)))
            self.assertEqual(m3.get_absolute_url(), reverse("market-results", args=(m3.slug,)))
            # Guess always goes to pending
            self.assertEqual(g1.get_absolute_url(), reverse("market-pending", args=(g1.pk,)))
            self.assertEqual(g2.get_absolute_url(), reverse("market-pending", args=(g2.pk,)))
            self.assertEqual(g3.get_absolute_url(), reverse("market-pending", args=(g3.pk,)))

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

            self.assertGet20X("market-guess", "guess-my-ssn")
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

            self.assertGet20X("market-guess", "guess-my-ssn")
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
            )
            self.assertHas(resp, "Change your guess")

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 500)
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
            self.assertEqual(guess.value, 500)
            self.assertAlmostEqual(guess.score, round((42 / 500) ** 2 * 2, ndigits=2))

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

            self.assertGet20X("market-guess", "guess-my-ssn")
            resp = self.assertPost20X(
                "market-guess", "guess-my-ssn", data={"value": 500}, follow=True
            )
            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 500)

            guess = Guess.objects.get(user__username="alice")
            self.assertEqual(guess.value, 500)
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
            self.assertEqual(guess.value, 500)
            self.assertAlmostEqual(guess.score, round((42 / 500) ** 3 * 2, ndigits=2))

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

    def test_student_redirects_to_guess_or_pending(self):
        market = Market.objects.get(slug="guess-my-ssn")
        from django.contrib.auth.models import Group
        verified_group, _ = Group.objects.get_or_create(name="Verified")
        with freeze_time("2050-07-01", tz_offset=0):
            # Student with no guess: should redirect to guess form
            student = UserFactory.create(username="bob", groups=(verified_group,))
            self.login(student)
            resp = self.client.get(self.url("market-results", "guess-my-ssn"), follow=True)
            self.assertRedirects(resp, self.url("market-guess", "guess-my-ssn"))

            # Student with guess: should redirect to pending
            GuessFactory.create(market=market, user=student, value=123)
            resp = self.client.get(self.url("market-results", "guess-my-ssn"), follow=True)
            guess = Guess.objects.get(market=market, user=student)
            self.assertRedirects(resp, self.url("market-pending", guess.pk))

    def test_admin_sees_results_page(self):
        market = Market.objects.get(slug="guess-my-ssn")
        admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)
        with freeze_time("2050-07-01", tz_offset=0):
            self.login(admin)
            resp = self.client.get(self.url("market-results", "guess-my-ssn"))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Market guess-my-ssn")


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
