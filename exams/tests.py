from core.factories import UserFactory
from django.test.utils import override_settings
from django.utils import timezone
from freezegun import freeze_time
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory

from exams.calculator import expr_compute
from exams.factories import TestFactory

UTC = timezone.utc


class ArithmeticTest(OTISTestCase):
	def checkCalculator(self, expr: str, out: float):
		v = expr_compute(expr)
		assert v is not None
		self.assertAlmostEquals(v, out)

	def test_arithmetic(self):
		self.checkCalculator('1/3^4', 1 / 81)
		self.checkCalculator('sin(pi)', 0)
		self.checkCalculator('sqrt(1/2)-cos(pi/4)', 0)
		self.checkCalculator('(2*sqrt(2))^2 - 4^(3/2)', 0)
		self.checkCalculator('16900/4*pi', 13273.2289614)

	def test_pdf(self):
		pass


class ExamTest(OTISTestCase):
	@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
	def test_pdf(self):
		alice = StudentFactory.create(semester__exam_family='Waltz')

		exam_waltz = TestFactory.create(
			start_date=timezone.datetime(2020, 1, 1, tzinfo=UTC),
			due_date=timezone.datetime(2020, 12, 31, tzinfo=UTC),
			family="Waltz",
		)
		exam_foxtrot = TestFactory.create(
			start_date=timezone.datetime(2020, 1, 1, tzinfo=UTC),
			due_date=timezone.datetime(2020, 12, 31, tzinfo=UTC),
			family="Foxtrot"
		)

		with freeze_time('2018-01-01', tz_offset=0):
			self.login(alice)
			self.assertGetDenied('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2020-06-05', tz_offset=0):
			self.login(alice)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2022-12-31', tz_offset=0):
			self.login(alice)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)

		bob = StudentFactory.create(semester__exam_family='Waltz', enabled=False)
		with freeze_time('2020-06-05', tz_offset=0):
			self.login(bob)
			self.assertGetDenied('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)

		staff = UserFactory.create(is_staff=True)
		with freeze_time('2018-01-01', tz_offset=0):
			self.login(staff)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGet20X('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2020-06-05', tz_offset=0):
			self.login(staff)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGet20X('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2040-12-31', tz_offset=0):
			self.login(staff)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGet20X('exam-pdf', exam_foxtrot.pk)
