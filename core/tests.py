from django.test import TestCase

from core.models import Semester


class TestSemester(TestCase):
	fixtures = ('testdata.yaml', )

	def test_semester_url(self):
		semester1 = Semester.objects.get(pk=1)
		self.assertEqual(f'/dash/past/{semester1.pk}/', semester1.get_absolute_url())
		semester2 = Semester.objects.get(pk=2)
		self.assertEqual(f'/dash/past/{semester2.pk}/', semester2.get_absolute_url())
