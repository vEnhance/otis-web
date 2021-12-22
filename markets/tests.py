from core.factories import UserFactory
from django.utils import timezone
from freezegun import freeze_time
from otisweb.tests import OTISTestCase

from markets.factories import MarketFactory
from markets.models import Guess, Market

utc = timezone.utc


class MarketModelTests(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		MarketFactory.create(
			start_date=timezone.datetime(2000, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2000, 1, 3, tzinfo=utc),
			slug='m-one',
		)
		MarketFactory.create(
			start_date=timezone.datetime(2020, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2020, 1, 3, tzinfo=utc),
			slug='m-two',
		)
		MarketFactory.create(
			start_date=timezone.datetime(2050, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2050, 1, 3, tzinfo=utc),
			slug='m-three',
		)

	def test_managers(self):
		with freeze_time('2020-01-02', tz_offset=0):
			self.assertEqual(Market.started.count(), 2)
			self.assertEqual(Market.active.count(), 1)
			self.assertEqual(Market.active.get().slug, 'm-two')

	def test_list(self):
		with freeze_time('2020-01-02', tz_offset=0):
			self.login(UserFactory.create())
			response = self.get('market-list')
			self.assertContains(response, 'm-one')
			self.assertContains(response, 'm-two')
			self.assertNotContains(response, 'm-three')


class MarketTests(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		MarketFactory(
			start_date=timezone.datetime(2050, 5, 1, 0, 0, 0, tzinfo=utc),
			end_date=timezone.datetime(2050, 9, 30, 23, 59, 59, tzinfo=utc),
			weight=2,
			alpha=2,
			slug='guess-my-ssn'
		)
		UserFactory(username='alice')

	def test_has_started(self):
		market = Market.objects.get(slug='guess-my-ssn')
		with freeze_time('2050-01-01', tz_offset=0):
			self.assertFalse(market.has_started)
		with freeze_time('2050-07-01', tz_offset=0):
			self.assertTrue(market.has_started)
		with freeze_time('2050-11-01', tz_offset=0):
			self.assertTrue(market.has_started)

	def test_has_ended(self):
		market = Market.objects.get(slug='guess-my-ssn')
		with freeze_time('2050-01-01', tz_offset=0):
			self.assertFalse(market.has_ended)
		with freeze_time('2050-07-01', tz_offset=0):
			self.assertFalse(market.has_ended)
		with freeze_time('2050-11-01', tz_offset=0):
			self.assertTrue(market.has_ended)

	def test_results_perms(self):
		with freeze_time('2050-01-01', tz_offset=0):
			self.login('alice')
			self.assertGet40X('market-results', 'guess-my-ssn')
		with freeze_time('2050-07-01', tz_offset=0):
			self.login('alice')
			resp = self.assertGet20X('market-results', 'guess-my-ssn')
			self.assertEqual(
				resp.request['PATH_INFO'],
				"/markets/guess/guess-my-ssn/",
			)
		with freeze_time('2050-11-01', tz_offset=0):
			self.login('alice')
			self.assertGet20X('market-results', 'guess-my-ssn')

	def test_guess_perms(self):
		with freeze_time('2050-01-01', tz_offset=0):
			self.login('alice')
			self.assertGet40X('market-guess', 'guess-my-ssn')
		with freeze_time('2050-07-01', tz_offset=0):
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertEqual(
				resp.request['PATH_INFO'],
				"/markets/guess/guess-my-ssn/",
			)
			self.assertContains(resp, "market main page")
		with freeze_time('2050-11-01', tz_offset=0):
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertEqual(
				resp.request['PATH_INFO'],
				"/markets/results/guess-my-ssn/",
			)

	def test_guess_form_with_answer(self):
		with freeze_time('2050-07-01', tz_offset=0):
			market = Market.objects.get(slug='guess-my-ssn')
			market.answer = 42
			market.save()
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "market main page")
			self.assertPost20X('market-guess', 'guess-my-ssn', data={'value': 100})

			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "You already submitted")

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertAlmostEqual(guess.score, round((42 / 100)**2 * 2, ndigits=2))

	def test_guess_form_without_answer(self):
		with freeze_time('2050-07-01', tz_offset=0):
			market = Market.objects.get(slug='guess-my-ssn')
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "market main page")
			self.assertPost20X('market-guess', 'guess-my-ssn', data={'value': 100})

			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "You already submitted")

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertEqual(guess.score, None)

			market.answer = 42
			market.save()
			self.assertPost40X('market-recompute', 'guess-my-ssn')

			UserFactory.create(username='admin', is_staff=True, is_superuser=True)
			self.login('admin')
			self.assertPost20X('market-recompute', 'guess-my-ssn')

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertAlmostEqual(guess.score, round((42 / 100)**2 * 2, ndigits=2))

	def test_guess_form_without_alpha(self):
		with freeze_time('2050-07-01', tz_offset=0):
			market = Market.objects.get(slug='guess-my-ssn')
			market.alpha = None
			market.save()
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertNotContains(resp, "market main page")  # because it's a special market
			self.assertPost20X('market-guess', 'guess-my-ssn', data={'value': 100})

			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "You already submitted")

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertEqual(guess.score, None)

			market.answer = 42
			market.alpha = 3
			market.save()
			self.assertPost40X('market-recompute', 'guess-my-ssn')

			UserFactory.create(username='admin', is_staff=True, is_superuser=True)
			self.login('admin')
			self.assertPost20X('market-recompute', 'guess-my-ssn')

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertAlmostEqual(guess.score, round((42 / 100)**3 * 2, ndigits=2))
