from core.factories import UnitFactory
from otisweb.tests import OTISTestCase

from roster.factories import StudentFactory

from .views import get_checksum


class RosterTest(OTISTestCase):
	def test_checksum_works(self):
		alice = StudentFactory.create(user__username='alice')
		self.assertEqual(len(get_checksum(alice)), 36)

	def test_curriculum(self):
		# TODO rewrite
		pass

	def test_finalize(self):
		bob = StudentFactory.create(user__username='bob', newborn=True)
		self.login('bob')
		self.assertContains(
			self.post('finalize', bob.pk, data={'submit': True}), 'You should select some units'
		)
		units = UnitFactory.create_batch(20)
		bob.curriculum.set(units)
		self.assertContains(
			self.post('finalize', bob.pk, data={}), 'Your curriculum has been finalized!'
		)
		self.assertEqual(bob.unlocked_units.count(), 3)
