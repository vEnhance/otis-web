from dashboard.models import PSet
from django.contrib.auth.models import User
from otisweb.tests import OTISTestCase
from roster.models import Assistant, Student

from core.models import Semester, Unit


class TestCore(OTISTestCase):
	@classmethod
	def setUpTestData(cls: Type[OTISTestCase]):
		assistant = Assistant.objects.create(user=User.objects.get(username='staff'))
		alice = Student.objects.create(
			user=User.objects.get(username='alice'),
			track='C',
			assistant=assistant,
			semester=Semester.objects.get(pk=1)
		)
		PSet.objects.create(unit=Unit.objects.get(pk=10), student=alice, approved=True)
		PSet.objects.create(unit=Unit.objects.get(pk=25), student=alice, approved=False)
		alice.unlocked_units.add(Unit.objects.get(pk=25))
		alice.unlocked_units.add(Unit.objects.get(pk=40))

	def test_semester_url(self):
		for sem in Semester.objects.all():
			self.assertEqual(f'/dash/past/{sem.pk}/', sem.get_absolute_url())
		self.assertGreater(Semester.objects.count(), 0)

	def test_views_login_redirect(self):
		self.assertGetBecomesLoginRedirect('view-problems', 10)
		self.assertGetBecomesLoginRedirect('view-solutions', 10)
		self.assertGetBecomesLoginRedirect('view-tex', 10)

	def test_alice_core_views(self):
		self.login('alice')
		self.assertGet20X('view-problems', 10)
		self.assertGet20X('view-problems', 25)
		self.assertGet20X('view-problems', 40)
		self.assertGet20X('view-tex', 10)
		self.assertGet20X('view-tex', 25)
		self.assertGet20X('view-tex', 40)
		self.assertGet20X('view-solutions', 10)
		self.assertGet20X('view-solutions', 25)
		self.assertGetDenied('view-solutions', 40)
		for v in ('view-problems', 'view-tex', 'view-solutions'):
			self.assertGetDenied(v, 55)

	def test_staff_core_views(self):
		self.login('staff')
		for v in ('view-problems', 'view-tex', 'view-solutions'):
			self.assertGet20X(v, 10)

	def test_mallory_core_views(self):
		self.login('mallory')
		for v in ('view-problems', 'view-tex', 'view-solutions'):
			self.assertGetDenied(v, 10)

	def test_classroom_url_works(self):
		self.login('mallory')
		self.assertGetOK('classroom')
