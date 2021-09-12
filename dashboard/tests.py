from exams.factories import ExamAttemptFactory, ExamFactory
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory
from roster.models import Student

from dashboard.factories import AchievementFactory, AchievementUnlockFactory, LevelFactory, PSetFactory, QuestCompleteFactory  # NOQA
from dashboard.levelsys import get_student_rows
from dashboard.views import annotate_student_queryset_with_scores, get_meters


class TestDashboard(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		alice = StudentFactory.create(user__first_name="Alice", user__last_name="Aardvark")
		PSetFactory.create(student=alice, clubs=120, hours=37, approved=True, unit__code='BGW')
		PSetFactory.create(student=alice, clubs=100, hours=20, approved=True, unit__code='DMX')
		PSetFactory.create(student=alice, clubs=180, hours=27, approved=True, unit__code='ZCY')
		PSetFactory.create(student=alice, clubs=200, hours=87, approved=False, unit__code='HMR')
		AchievementUnlockFactory.create(
			user=alice.user, achievement__diamonds=4, achievement__name="Feel the fours"
		)
		AchievementUnlockFactory.create(
			user=alice.user, achievement__diamonds=7, achievement__name="Lucky number"
		)
		ExamAttemptFactory.create(student=alice, score=3)
		ExamAttemptFactory.create(student=alice, score=4)
		QuestCompleteFactory.create(student=alice, spades=5, title="Not problem six")
		LevelFactory.create_batch(size=50)

	def get_alice(self):
		return Student.objects.get(user__first_name="Alice", user__last_name="Aardvark")

	def test_portal_loads(self):
		alice = StudentFactory.create()
		self.login(alice)
		self.assertGet20X('portal', alice.pk)

	def test_meter_update(self):
		alice = self.get_alice()
		data = get_meters(alice)
		self.assertEqual(data['meters']['clubs'].level, 22)
		self.assertEqual(data['meters']['clubs'].value, 520)
		self.assertEqual(data['meters']['hearts'].level, 9)
		self.assertEqual(data['meters']['hearts'].value, 84)
		self.assertEqual(data['meters']['diamonds'].level, 3)
		self.assertEqual(data['meters']['diamonds'].value, 11)
		self.assertEqual(data['meters']['spades'].level, 3)
		self.assertEqual(data['meters']['spades'].value, 12)
		self.assertEqual(data['level_number'], 37)
		self.assertEqual(data['level_name'], 'Level 37')

	def test_portal_stats(self):
		alice = self.get_alice()
		self.login(alice)
		resp = self.get('portal', alice.pk)
		self.assertContains(resp, 'Level 37')
		self.assertContains(resp, '520♣')
		self.assertContains(resp, '84♥')
		self.assertContains(resp, '11◆')
		self.assertContains(resp, '12♠')

	def test_stats_page(self):
		alice = self.get_alice()
		self.login(alice)
		bob = StudentFactory.create()
		AchievementUnlockFactory.create(user=bob.user, achievement__name="FAIL THIS TEST")
		QuestCompleteFactory.create(student=bob, title="FAIL THIS TEST")

		resp = self.get('stats', alice.pk)
		self.assertContains(resp, 'Level 37')
		self.assertContains(resp, '520♣')
		self.assertContains(resp, '84♥')
		self.assertContains(resp, '11◆')
		self.assertContains(resp, '12♠')
		self.assertContains(resp, 'Feel the fours')
		self.assertContains(resp, 'Not problem six')
		self.assertContains(resp, 'Lucky number')
		self.assertNotContains(resp, 'FAIL THIS TEST')

	def test_multi_student_annotate(self):
		alice = self.get_alice()
		bob = StudentFactory.create()
		carol = StudentFactory.create()
		donald = StudentFactory.create()

		# problem sets (clubs/hearts)
		PSetFactory.create(student=bob, clubs=196, hours=64, approved=True, unit__code='BMW')
		PSetFactory.create(student=bob, clubs=None, hours=None, approved=True, unit__code='ZMY')

		# diamonds
		a1 = AchievementFactory.create(diamonds=3)
		a2 = AchievementFactory.create(diamonds=6)
		AchievementUnlockFactory.create(user=carol.user, achievement=a1)
		AchievementUnlockFactory.create(user=carol.user, achievement=a2)
		AchievementUnlockFactory.create(user=bob.user, achievement=a2)

		# spades
		exam = ExamFactory.create()
		ExamAttemptFactory.create(student=bob, score=3, quiz=exam)
		ExamAttemptFactory.create(student=carol, score=4, quiz=exam)
		ExamAttemptFactory.create(student=carol, score=2)
		QuestCompleteFactory.create(student=carol, spades=5)

		# make levels
		LevelFactory.create_batch(size=36)

		queryset = annotate_student_queryset_with_scores(Student.objects.all())
		alice = queryset.get(pk=alice.pk)
		bob = queryset.get(pk=bob.pk)
		carol = queryset.get(pk=carol.pk)
		donald = queryset.get(pk=donald.pk)

		self.assertEqual(getattr(alice, 'num_psets'), 3)
		self.assertEqual(getattr(alice, 'clubs_any'), 400)
		self.assertEqual(getattr(alice, 'clubs_D'), 100)
		self.assertEqual(getattr(alice, 'clubs_Z'), 180)
		self.assertEqual(getattr(alice, 'hearts'), 84)
		self.assertEqual(getattr(alice, 'spades_quizzes'), 7)
		self.assertEqual(getattr(alice, 'spades_quests'), 5)
		self.assertEqual(getattr(alice, 'diamonds'), 11)

		self.assertEqual(getattr(bob, 'num_psets'), 2)
		self.assertEqual(getattr(bob, 'clubs_any'), 196)
		self.assertEqual(getattr(bob, 'clubs_D'), None)
		self.assertEqual(getattr(bob, 'clubs_Z'), None)
		self.assertEqual(getattr(bob, 'hearts'), 64)
		self.assertEqual(getattr(bob, 'spades_quizzes'), 3)
		self.assertEqual(getattr(bob, 'spades_quests'), None)
		self.assertEqual(getattr(bob, 'diamonds'), 6)

		self.assertEqual(getattr(carol, 'num_psets'), 0)
		self.assertEqual(getattr(carol, 'clubs_any'), None)
		self.assertEqual(getattr(carol, 'clubs_D'), None)
		self.assertEqual(getattr(carol, 'clubs_Z'), None)
		self.assertEqual(getattr(carol, 'hearts'), None)
		self.assertEqual(getattr(carol, 'spades_quizzes'), 6)
		self.assertEqual(getattr(carol, 'spades_quests'), 5)
		self.assertEqual(getattr(carol, 'diamonds'), 9)

		self.assertEqual(getattr(donald, 'num_psets'), 0)
		self.assertEqual(getattr(donald, 'clubs_any'), None)
		self.assertEqual(getattr(donald, 'clubs_D'), None)
		self.assertEqual(getattr(donald, 'clubs_Z'), None)
		self.assertEqual(getattr(donald, 'hearts'), None)
		self.assertEqual(getattr(donald, 'spades_quizzes'), None)
		self.assertEqual(getattr(donald, 'spades_quests'), None)
		self.assertEqual(getattr(donald, 'diamonds'), None)

		rows = get_student_rows(queryset)
		rows.sort(key=lambda row: row['student'].pk)

		self.assertEqual(rows[0]['clubs'], 520)
		self.assertEqual(rows[0]['hearts'], 84)
		self.assertEqual(rows[0]['spades'], 12)
		self.assertEqual(rows[0]['diamonds'], 11)
		self.assertEqual(rows[0]['level'], 37)
		self.assertEqual(rows[0]['level_name'], 'Level 37')

		self.assertEqual(rows[1]['clubs'], 196)
		self.assertEqual(rows[1]['hearts'], 64)
		self.assertEqual(rows[1]['spades'], 3)
		self.assertEqual(rows[1]['diamonds'], 6)
		self.assertEqual(rows[1]['level'], 25)
		self.assertEqual(rows[1]['level_name'], 'Level 25')

		self.assertEqual(rows[2]['clubs'], 0)
		self.assertEqual(rows[2]['hearts'], 0)
		self.assertEqual(rows[2]['spades'], 11)
		self.assertEqual(rows[2]['diamonds'], 9)
		self.assertEqual(rows[2]['level'], 6)
		self.assertEqual(rows[2]['level_name'], 'Level 6')

		self.assertEqual(rows[3]['clubs'], 0)
		self.assertEqual(rows[3]['hearts'], 0)
		self.assertEqual(rows[3]['spades'], 0)
		self.assertEqual(rows[3]['diamonds'], 0)
		self.assertEqual(rows[3]['level'], 0)
		self.assertEqual(rows[3]['level_name'], "No level")
