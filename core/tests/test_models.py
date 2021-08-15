from core.models import Semester
from django.test import TestCase


class TestSemester(TestCase):
	def setUp(self):
		Semester.objects.create(
				name = "Year 0",
				active = True,
				exam_family = "Waltz",
				)
	def test_semester_url(self):
		semester = Semester.objects.get(name = "Year 0")
		self.assertEqual(f'/dash/past/{semester.pk}/', semester.get_absolute_url())
