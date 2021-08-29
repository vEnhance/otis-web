from exams.factories import ExamAttemptFactory
from otisweb.tests import OTISTestCase
from roster.factories import StudentFactory

from dashboard.factories import AchievementUnlockFactory, LevelFactory, PSetFactory  # NOQA
from dashboard.models import Level
from dashboard.views import get_meter_update


class TestMeters(OTISTestCase):
	def test_portal_loads(self):
		alice = StudentFactory.create()
		self.login(alice)
		self.assertGet20X('portal', alice.pk)

	def test_meter_update(self):
		alice = StudentFactory.create()
		PSetFactory.create(student=alice, clubs=120, hours=37, approved=True)
		PSetFactory.create(student=alice, clubs=180, hours=47, approved=True)
		PSetFactory.create(student=alice, clubs=240, hours=87, approved=False)
		AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=4)
		AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=7)
		ExamAttemptFactory.create(student=alice, score=3)
		ExamAttemptFactory.create(student=alice, score=4)
		LevelFactory.create_batch(size=32)

		data = get_meter_update(alice)
		self.assertEqual(data['meters']['clubs'].level, 17)
		self.assertEqual(data['meters']['clubs'].value, 300)
		self.assertEqual(data['meters']['hearts'].level, 9)
		self.assertEqual(data['meters']['hearts'].value, 84)
		self.assertEqual(data['meters']['diamonds'].level, 3)
		self.assertEqual(data['meters']['diamonds'].value, 11)
		self.assertEqual(data['meters']['spades'].level, 2)
		self.assertEqual(data['meters']['spades'].value, 7)
		self.assertEqual(data['level_number'], 31)
		self.assertEqual(data['level_name'], Level.objects.get(threshold=31).name)
