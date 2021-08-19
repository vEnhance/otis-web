from dashboard.models import PSet
from django.contrib.auth.models import User
from otisweb.tests import OTISTestCase
from roster.models import Assistant, Student

from core.models import Semester, Unit


class TestCore(OTISTestCase):
	@classmethod
	def setUpTestData(cls: type):
		assistant = Assistant.objects.create(user=User.objects.get(username='staff'))
		alice = Student.objects.create(
			user=User.objects.get(username='alice'),
			track='C',
			assistant=assistant,
			semester=Semester.objects.get(pk=1)
		)
		PSet.objects.create(unit=Unit.objects.get(pk=1), student=alice, approved=True)
		PSet.objects.create(unit=Unit.objects.get(pk=2), student=alice, approved=False)

	def test_semester_url(self):
		for sem in Semester.objects.all():
			self.assertEqual(f'/dash/past/{sem.pk}/', sem.get_absolute_url())
		self.assertGreater(Semester.objects.count(), 0)

	def test_permitted(self):
		self.assertGetBecomesLoginRedirect('view-problems', 1)
		self.login('alice')
		self.assertGet20X('view-problems', 1)
