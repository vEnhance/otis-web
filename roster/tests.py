from core.factories import UnitFactory, UnitGroupFactory
from otisweb.tests import OTISTestCase

from roster.factories import AssistantFactory, StudentFactory
from roster.models import Student

from .views import get_checksum


class RosterTest(OTISTestCase):
	def test_curriculum(self):
		staff = AssistantFactory.create(user__username='staff')
		alice = StudentFactory.create(user__username='alice', assistant=staff)

		unitgroups = UnitGroupFactory.create_batch(4)
		for unitgroup in unitgroups:
			for letter in 'BDZ':
				UnitFactory.create(code=letter + unitgroup.subject[0] + 'W', group=unitgroup)

		self.login('alice')
		self.assertContains(self.get('currshow', alice.pk), text="you are not an instructor")

		self.login('staff')
		self.assertNotContains(self.get('currshow', alice.pk), text="you are not an instructor")

		data = {
			'group-0': [1, ],
			'group-1': [4, 6],
			'group-3': [10, 11, 12],
		}
		self.post('currshow', alice.pk, data=data)
		self.assertEqual(len(Student.objects.get(pk=alice.pk).curriculum.all()), 6)

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

	def test_checksum_works(self):
		alice = StudentFactory.create(user__username='alice')
		self.assertEqual(len(get_checksum(alice)), 36)
