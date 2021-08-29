from exams.factories import ExamAttemptFactory, ExamFactory
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory
from roster.models import Student

from dashboard.factories import AchievementFactory, AchievementUnlockFactory, LevelFactory, PSetFactory, QuestCompleteFactory  # NOQA
from dashboard.models import Level
from dashboard.views import annotate_multiple_students, get_meter_update


class TestMeters(OTISTestCase):
	def test_portal_loads(self):
		alice = StudentFactory.create()
		self.login(alice)
		self.assertGet20X('portal', alice.pk)

	def setup_alice_example(self) -> Student:
		alice = StudentFactory.create()
		PSetFactory.create(student=alice, clubs=120, hours=37, approved=True)
		PSetFactory.create(student=alice, clubs=180, hours=47, approved=True)
		PSetFactory.create(student=alice, clubs=240, hours=87, approved=False)
		AchievementUnlockFactory.create(
			user=alice.user, achievement__diamonds=4, achievement__name="Feel the fours"
		)
		AchievementUnlockFactory.create(
			user=alice.user, achievement__diamonds=7, achievement__name="Lucky number"
		)
		ExamAttemptFactory.create(student=alice, score=3)
		ExamAttemptFactory.create(student=alice, score=4)
		QuestCompleteFactory.create(student=alice, spades=5, title="Not problem six")
		LevelFactory.reset_sequence(1)
		LevelFactory.create_batch(size=36)
		return alice

	def test_meter_update(self):
		alice = self.setup_alice_example()
		data = get_meter_update(alice)
		self.assertEqual(data['meters']['clubs'].level, 17)
		self.assertEqual(data['meters']['clubs'].value, 300)
		self.assertEqual(data['meters']['hearts'].level, 9)
		self.assertEqual(data['meters']['hearts'].value, 84)
		self.assertEqual(data['meters']['diamonds'].level, 3)
		self.assertEqual(data['meters']['diamonds'].value, 11)
		self.assertEqual(data['meters']['spades'].level, 3)
		self.assertEqual(data['meters']['spades'].value, 12)
		self.assertEqual(data['level_number'], 32)
		self.assertEqual(data['level_name'], Level.objects.get(threshold=32).name)

	def test_portal_stats(self):
		alice = self.setup_alice_example()
		self.login(alice)
		resp = self.get('portal', alice.pk)
		self.assertContains(resp, Level.objects.get(threshold=32).name)
		self.assertContains(resp, '300♣')
		self.assertContains(resp, '84♥')
		self.assertContains(resp, '11◆')
		self.assertContains(resp, '12♠')

	def test_stats_page(self):
		alice = self.setup_alice_example()
		self.login(alice)
		bob = StudentFactory.create()
		AchievementUnlockFactory.create(user=bob.user, achievement__name="FAIL THIS TEST")
		QuestCompleteFactory.create(student=bob, title="FAIL THIS TEST")

		resp = self.get('stats', alice.pk)
		self.assertContains(resp, Level.objects.get(threshold=32).name)
		self.assertContains(resp, '300♣')
		self.assertContains(resp, '84♥')
		self.assertContains(resp, '11◆')
		self.assertContains(resp, '12♠')
		self.assertContains(resp, 'Feel the fours')
		self.assertContains(resp, 'Not problem six')
		self.assertContains(resp, 'Lucky number')
		self.assertNotContains(resp, 'FAIL THIS TEST')

	def test_multi_student_annotate(self):
		alice = StudentFactory.create()
		bob = StudentFactory.create()
		carol = StudentFactory.create()
		donald = StudentFactory.create()

		# problem sets (clubs/hearts)
		PSetFactory.create(student=alice, clubs=120, hours=37, approved=True)
		PSetFactory.create(student=alice, clubs=180, hours=47, approved=True)
		PSetFactory.create(student=alice, clubs=240, hours=87, approved=False)
		PSetFactory.create(student=bob, clubs=196, hours=64, approved=True)
		PSetFactory.create(student=bob, clubs=None, hours=None, approved=True)

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
		QuestCompleteFactory.create(student=alice, spades=7)

		# make levels
		LevelFactory.create_batch(size=36)

		queryset = annotate_multiple_students(Student.objects.all())
		alice = queryset.get(pk=alice.pk)
		bob = queryset.get(pk=bob.pk)
		carol = queryset.get(pk=carol.pk)
		donald = queryset.get(pk=donald.pk)

		self.assertEqual(getattr(alice, 'num_psets'), 2)
		self.assertEqual(getattr(alice, 'clubs'), 300)
		self.assertEqual(getattr(alice, 'hearts'), 84)
		self.assertEqual(getattr(alice, 'spades_quizzes'), None)
		self.assertEqual(getattr(alice, 'spades_quests'), 7)
		self.assertEqual(getattr(alice, 'diamonds'), None)

		self.assertEqual(getattr(bob, 'num_psets'), 2)
		self.assertEqual(getattr(bob, 'clubs'), 196)
		self.assertEqual(getattr(bob, 'hearts'), 64)
		self.assertEqual(getattr(bob, 'spades_quizzes'), 3)
		self.assertEqual(getattr(bob, 'spades_quests'), None)
		self.assertEqual(getattr(bob, 'diamonds'), 6)

		self.assertEqual(getattr(carol, 'num_psets'), 0)
		self.assertEqual(getattr(carol, 'clubs'), None)
		self.assertEqual(getattr(carol, 'hearts'), None)
		self.assertEqual(getattr(carol, 'spades_quizzes'), 6)
		self.assertEqual(getattr(carol, 'spades_quests'), 5)
		self.assertEqual(getattr(carol, 'diamonds'), 9)

		self.assertEqual(getattr(donald, 'num_psets'), 0)
		self.assertEqual(getattr(donald, 'clubs'), None)
		self.assertEqual(getattr(donald, 'hearts'), None)
		self.assertEqual(getattr(donald, 'spades_quizzes'), None)
		self.assertEqual(getattr(donald, 'spades_quests'), None)
		self.assertEqual(getattr(donald, 'diamonds'), None)
