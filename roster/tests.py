from typing import Type

from core.models import Semester, Unit
from dashboard.models import PSet
from django.contrib.auth.models import User
from otisweb.tests import OTISTestCase

from roster.models import Assistant, Student

from .views import get_checksum


class RosterTest(OTISTestCase):
	@classmethod
	def setUpTestData(cls: Type[OTISTestCase]):
		assistant = Assistant.objects.create(user=User.objects.get(username='staff'))
		alice = Student.objects.create(
			user=User.objects.get(username='alice'),
			semester=Semester.objects.get(pk=2),
			track='C',
			assistant=assistant,
			newborn=False
		)
		alice.curriculum.add(*[i for i in range(10, 101, 10)])
		alice.unlocked_units.add(20, 30, 40)
		PSet.objects.create(unit=Unit.objects.get(pk=10), student=alice, approved=True)
		PSet.objects.create(unit=Unit.objects.get(pk=20), student=alice, approved=False)

	def test_checksum_works(self):
		alice: Student = Student.objects.get(user__username='alice')
		self.assertEqual(len(get_checksum(alice)), 36)

	def test_curriculum(self):
		alice: Student = Student.objects.get(user__username='alice')
		self.login('alice')
		self.assertContains(self.get('currshow', alice.pk), "since you are not an instructor")
		self.assertPostOK('currshow', alice.pk, data={'group-0': 117, 'group-77': 94})
		self.assertEqual(alice.curriculum_length, 10)

		self.login('staff')
		self.assertNotContains(self.get('currshow', alice.pk), "since you are not an instructor")
		self.assertPostOK('currshow', alice.pk, data={'group-0': 117, 'group-77': 94})
		self.assertEqual(alice.curriculum_length, 2)

	def test_finalize(self):
		bob: Student = Student.objects.create(
			user=User.objects.get(username='bob'),
			semester=Semester.objects.get(pk=2),
			newborn=True,
		)
		self.login('bob')
		self.assertContains(
			self.post('finalize', bob.pk, data={'submit': True}), 'You should select some units'
		)
		bob.curriculum.add(10, 20, 30, 40, 50)
		self.assertContains(
			self.post('finalize', bob.pk, data={}), 'Your curriculum has been finalized!'
		)
		self.assertEqual(bob.unlocked_units.count(), 3)

	def test_advance(self):
		pass
