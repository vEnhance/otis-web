from core.factories import UserFactory
from django.utils import timezone
from freezegun import freeze_time
from otisweb.tests import OTISTestCase

from markets.factories import MarketFactory
from markets.models import Guess, Market

utc = timezone.utc


class MarketModelTests(OTISTestCase):
	def test_started_maanger(self):
		MarketFactory.create(
			start_date=timezone.datetime(2000, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2000, 1, 3, tzinfo=utc),
		)
		MarketFactory.create(
			start_date=timezone.datetime(2020, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2020, 1, 3, tzinfo=utc),
		)
		MarketFactory.create(
			start_date=timezone.datetime(2050, 1, 1, tzinfo=utc),
			end_date=timezone.datetime(2050, 1, 3, tzinfo=utc),
		)
		self.assertEqual(Market.started.count(), 2)


class MarketTests(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		MarketFactory(
			start_date=timezone.datetime(2050, 5, 1, 0, 0, 0, tzinfo=utc),
			end_date=timezone.datetime(2050, 9, 30, 23, 59, 59, tzinfo=utc),
			answer=42,  # yes, my SSN is 42, get rekt
			weight=2,
			alpha=2,
			slug='guess-my-ssn'
		)
		UserFactory(username='alice')

	def test_is_started(self):
		market = Market.objects.get(slug='guess-my-ssn')
		with freeze_time('2050-01-01', tz_offset=0):
			self.assertFalse(market.is_started)
		with freeze_time('2050-07-01', tz_offset=0):
			self.assertTrue(market.is_started)
		with freeze_time('2050-11-01', tz_offset=0):
			self.assertTrue(market.is_started)

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
			self.assertGet40X('market-results', 'guess-my-ssn')
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
			self.assertContains(resp, "Results are revealed")
		with freeze_time('2050-11-01', tz_offset=0):
			self.login('alice')
			# should redirect to market-results
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "The correct answer was")

	def test_guess_form(self):
		with freeze_time('2050-07-01', tz_offset=0):
			self.login('alice')
			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "Results are revealed")
			self.assertPost20X('market-guess', 'guess-my-ssn', data={'value': 100})

			resp = self.assertGet20X('market-guess', 'guess-my-ssn')
			self.assertContains(resp, "You already submitted")

			guess = Guess.objects.get(user__username='alice')
			self.assertEqual(guess.value, 100)
			self.assertAlmostEqual(guess.score, round((42 / 100)**2 * 2, ndigits=2))
