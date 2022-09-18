from core.factories import UserFactory
from django.contrib.auth.models import User
from django.test.utils import override_settings
from django.utils import timezone
from freezegun import freeze_time
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory

from exams.calculator import expr_compute
from exams.factories import QuizFactory, TestFactory
from exams.models import ExamAttempt, PracticeExam

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
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		StudentFactory.create(user__username="alice", semester__exam_family='Waltz')
		StudentFactory.create(
			user__username="disabled", enabled=False, semester__exam_family='Waltz'
		)

		with override_settings(TESTING_NEEDS_MOCK_MEDIA=True):
			for factory in (TestFactory, QuizFactory):
				for family in ("Waltz", "Foxtrot"):
					factory.create(
						start_date=timezone.datetime(2020, 1, 1, tzinfo=UTC),
						due_date=timezone.datetime(2020, 12, 31, tzinfo=UTC),
						family=family,
						number=1,
					)
		PracticeExam.objects.filter(is_test=False).update(
			answer1=1000,
			answer2=2000,
			answer3=3000,
			answer4=4000,
			answer5=5000,
		)

	def test_exam_pdf(self):
		exam_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
		exam_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

		with freeze_time('2018-01-01', tz_offset=0):
			self.login('alice')
			self.assertGetDenied('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2020-06-05', tz_offset=0):
			self.login('alice')
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)
		with freeze_time('2022-12-31', tz_offset=0):
			self.login('alice')
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGetDenied('exam-pdf', exam_foxtrot.pk)

		with freeze_time('2020-06-05', tz_offset=0):
			self.login('disabled')
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
		with freeze_time('2022-12-31', tz_offset=0):
			self.login(staff)
			self.assertGet20X('exam-pdf', exam_waltz.pk)
			self.assertGet20X('exam-pdf', exam_foxtrot.pk)

	def test_quiz(self):
		alice = User.objects.get(username='alice')
		quiz_waltz = PracticeExam.objects.get(family="Waltz", is_test=False)
		quiz_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=False)
		test_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
		test_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

		with freeze_time('2018-01-01', tz_offset=0):
			self.login('alice')
			self.assertGetDenied('quiz', alice.pk, quiz_waltz.pk)
			self.assertGetDenied('quiz', alice.pk, test_waltz.pk)
			self.assertGetDenied('quiz', alice.pk, test_foxtrot.pk)
			self.assertGetDenied('quiz', alice.pk, quiz_foxtrot.pk)
		with freeze_time('2020-06-05', tz_offset=0):
			self.login('disabled')
			self.assertGetDenied('quiz', User.objects.get(username='disabled').pk, quiz_waltz.pk)
			self.login('alice')
			self.assertGetDenied('quiz', alice.pk, test_waltz.pk)
			self.assertGetDenied('quiz', alice.pk, test_foxtrot.pk)
			self.assertGetDenied('quiz', alice.pk, quiz_foxtrot.pk)

			# OK, now actually take a quiz, lol
			resp_before_submit = self.assertGet20X('quiz', alice.pk, quiz_waltz.pk)
			self.assertHas(resp_before_submit, "Submit answers")
			resp_after_submit = self.assertPost20X(
				'quiz',
				alice.pk,
				quiz_waltz.pk,
				data={
					'guess1': 1337,
					'guess2': 2016,
					'guess3': 3000,
					'guess4': 4000,
				}
			)
			self.assertHas(resp_after_submit, "1337", count=1)
			self.assertHas(resp_after_submit, "2020", count=1)
			self.assertHas(resp_after_submit, "1000", count=1)
			self.assertHas(resp_after_submit, "2000", count=1)
			self.assertHas(resp_after_submit, "3000", count=2)
			self.assertHas(resp_after_submit, "4000", count=2)
			self.assertHas(resp_after_submit, "5000", count=1)
			self.assertPost40X(
				'quiz',
				alice.pk,
				quiz_waltz.pk,
				data={
					'answer1': 1337,
					'answer2': 2016,
					'answer3': 3000,
					'answer4': 4000,
				}
			)
			a = ExamAttempt.objects.get(student__user__username='alice')
			self.assertEqual(a.score, 2)
			self.assertEqual(a.guess1, "1337")
			self.assertEqual(a.guess2, "2016")
			self.assertEqual(a.guess3, "3000")
			self.assertEqual(a.guess4, "4000")
			self.assertEqual(a.guess5, "")

		with freeze_time('2022-12-31', tz_offset=0):
			self.login('alice')

	def test_mocks(self):
		self.login('disabled')
		self.assertGetDenied('mocks', follow=True)

		self.login('alice')
		resp = self.assertGet20X('mocks', follow=True)
		self.assertHas(resp, 'Waltz Test 01')
