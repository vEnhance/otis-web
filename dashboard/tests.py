import os
from io import StringIO

from core.factories import UnitFactory, UserFactory
from django.utils import timezone
from evans_django_tools.testsuite import EvanTestCase
from exams.factories import ExamAttemptFactory, TestFactory
from roster.factories import StudentFactory
from roster.models import Student

from dashboard.factories import AchievementFactory, AchievementUnlockFactory, BonusLevelFactory, LevelFactory, PSetFactory, QuestCompleteFactory  # NOQA
from dashboard.levelsys import get_student_rows
from dashboard.models import PSet
from dashboard.utils import get_units_to_submit, get_units_to_unlock
from dashboard.views import annotate_student_queryset_with_scores, get_level_info  # NOQA

utc = timezone.utc


class TestLevelSystem(EvanTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		alice = StudentFactory.create(user__first_name="Alice", user__last_name="Aardvark")
		PSetFactory.create(student=alice, clubs=120, hours=37, status='A', unit__code='BGW')
		PSetFactory.create(student=alice, clubs=100, hours=20, status='A', unit__code='DMX')
		PSetFactory.create(student=alice, clubs=180, hours=27, status='A', unit__code='ZCY')
		PSetFactory.create(student=alice, clubs=200, hours=87, status='P', unit__code='ZMR')
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
		data = get_level_info(alice)
		self.assertEqual(data['meters']['clubs'].level, 22)
		self.assertEqual(data['meters']['clubs'].value, 520)
		self.assertEqual(data['meters']['hearts'].level, 9)
		self.assertEqual(data['meters']['hearts'].value, 84)
		self.assertEqual(data['meters']['diamonds'].level, 3)
		self.assertEqual(data['meters']['diamonds'].value, 11)
		self.assertEqual(data['meters']['spades'].level, 4)
		self.assertEqual(data['meters']['spades'].value, 19)
		self.assertEqual(data['level_number'], 38)
		self.assertEqual(data['level_name'], 'Level 38')

	def test_portal_stats(self):
		alice = self.get_alice()
		self.login(alice)
		resp = self.get('portal', alice.pk)
		self.assertHas(resp, 'Level 38')
		self.assertHas(resp, '520♣')
		self.assertHas(resp, '84♥')
		self.assertHas(resp, '11◆')
		self.assertHas(resp, '19♠')

	def test_stats_page(self):
		alice = self.get_alice()
		self.login(alice)
		bob = StudentFactory.create()
		AchievementUnlockFactory.create(user=bob.user, achievement__name="FAIL THIS TEST")
		QuestCompleteFactory.create(student=bob, title="FAIL THIS TEST")

		resp = self.get('stats', alice.pk)
		self.assertHas(resp, 'Level 38')
		self.assertHas(resp, '520♣')
		self.assertHas(resp, '84♥')
		self.assertHas(resp, '11◆')
		self.assertHas(resp, '19♠')
		self.assertHas(resp, 'Feel the fours')
		self.assertHas(resp, 'Not problem six')
		self.assertHas(resp, 'Lucky number')
		self.assertNotHas(resp, 'FAIL THIS TEST')

	def test_level_up(self):
		alice = self.get_alice()
		self.login(alice)
		bonus = BonusLevelFactory.create(group__name="Level 40 Quest", level=40)
		bonus_unit = UnitFactory.create(group=bonus.group, code='DKU')

		resp = self.assertGet20X('portal', alice.pk)
		self.assertHas(resp, "You&#x27;re now level 38.")
		self.assertNotHas(resp, "Level 40 Quest")

		resp = self.assertGet20X('portal', alice.pk)
		self.assertNotHas(resp, "You&#x27;re now level 38.")
		self.assertNotHas(resp, "Level 40 Quest")

		QuestCompleteFactory.create(student=alice, spades=24)

		resp = self.assertGet20X('portal', alice.pk)
		self.assertHas(resp, "You&#x27;re now level 40.")
		self.assertHas(resp, "Level 40 Quest")

		resp = self.assertGet20X('portal', alice.pk)
		self.assertNotHas(resp, "You&#x27;re now level 40.")
		self.assertHas(resp, "Level 40 Quest")

		QuestCompleteFactory.create(student=alice, spades=64)
		alice.curriculum.remove(bonus_unit)

		resp = self.assertGet20X('portal', alice.pk)
		self.assertHas(resp, "You&#x27;re now level 44.")
		self.assertNotHas(resp, "Level 40 Quest")

	def test_multi_student_annotate(self):
		alice = self.get_alice()
		bob = StudentFactory.create()
		carol = StudentFactory.create()
		donald = StudentFactory.create()

		# problem sets (clubs/hearts)
		PSetFactory.create(student=bob, clubs=196, hours=64, status='A', unit__code='DMW')
		PSetFactory.create(student=bob, clubs=None, hours=None, status='A', unit__code='ZMY')

		# diamonds
		a1 = AchievementFactory.create(diamonds=3)
		a2 = AchievementFactory.create(diamonds=6)
		AchievementUnlockFactory.create(user=carol.user, achievement=a1)
		AchievementUnlockFactory.create(user=carol.user, achievement=a2)
		AchievementUnlockFactory.create(user=bob.user, achievement=a2)

		# spades
		exam = TestFactory.create()
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
		self.assertEqual(getattr(bob, 'clubs_D'), 196)
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
		self.assertEqual(rows[0]['spades'], 19)
		self.assertEqual(rows[0]['diamonds'], 11)
		self.assertEqual(rows[0]['level'], 38)
		self.assertEqual(rows[0]['level_name'], 'Level 38')
		self.assertAlmostEqual(rows[0]['insanity'], 0.25)

		self.assertAlmostEqual(rows[1]['clubs'], 254.8)
		self.assertEqual(rows[1]['hearts'], 64)
		self.assertEqual(rows[1]['spades'], 6)
		self.assertEqual(rows[1]['diamonds'], 6)
		self.assertEqual(rows[1]['level'], 27)
		self.assertEqual(rows[1]['level_name'], 'Level 27')
		self.assertAlmostEqual(rows[1]['insanity'], 0.5)

		self.assertEqual(rows[2]['clubs'], 0)
		self.assertEqual(rows[2]['hearts'], 0)
		self.assertEqual(rows[2]['spades'], 17)
		self.assertEqual(rows[2]['diamonds'], 9)
		self.assertEqual(rows[2]['level'], 7)
		self.assertEqual(rows[2]['level_name'], 'Level 7')
		self.assertAlmostEqual(rows[2]['insanity'], 0)

		self.assertEqual(rows[3]['clubs'], 0)
		self.assertEqual(rows[3]['hearts'], 0)
		self.assertEqual(rows[3]['spades'], 0)
		self.assertEqual(rows[3]['diamonds'], 0)
		self.assertEqual(rows[3]['level'], 0)
		self.assertEqual(rows[3]['level_name'], "No level")
		self.assertAlmostEqual(rows[3]['insanity'], 0)

		admin = UserFactory.create(is_staff=True, is_superuser=True)
		self.login(admin)
		self.assertGet20X('leaderboard')


class TestSubmitPSet(EvanTestCase):
	def test_submit(self):
		unit1 = UnitFactory.create(code='BMW')
		unit2 = UnitFactory.create(code='DMX')
		unit3 = UnitFactory.create(code='ZMY')
		alice = StudentFactory.create()
		self.login(alice)
		alice.unlocked_units.add(unit1)
		alice.curriculum.set([unit1, unit2, unit3])

		# Alice should show initially as Level 0
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 0')

		# Alice submits a problem set
		content1 = StringIO('Meow')
		content1.name = 'content1.txt'
		resp = self.assertPost20X(
			'submit-pset',
			alice.pk,
			data={
				'unit': unit1.pk,
				'clubs': 13,
				'hours': 37,
				'feedback': 'hello',
				'special_notes': 'meow',
				'content': content1,
				'next_unit_to_unlock': unit2.pk
			},
			follow=True
		)
		self.assertHas(resp, '13♣')
		self.assertHas(resp, '37.0♥')
		self.assertHas(resp, 'This unit submission is pending review')

		# Alice should still be Level 0 though
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 0')

		# Check pset reflects this data
		pset = PSet.objects.get(student=alice, unit=unit1)
		self.assertEqual(pset.clubs, 13)
		self.assertEqual(pset.hours, 37)
		self.assertEqual(pset.feedback, 'hello')
		self.assertEqual(pset.special_notes, 'meow')
		self.assertEqual(os.path.basename(pset.upload.content.name), 'content1.txt')
		self.assertFalse(pset.accepted)
		self.assertFalse(pset.resubmitted)

		# Alice realizes she made a typo in hours and edits the problem set
		content2 = StringIO('Purr')
		content2.name = 'content2.txt'
		resp = self.assertPost20X(
			'resubmit-pset',
			alice.pk,
			data={
				'unit': unit1.pk,
				'clubs': 13,
				'hours': 3.7,
				'feedback': 'hello',
				'special_notes': 'meow',
				'content': content2,
				'next_unit_to_unlock': unit3.pk
			},
			follow=True
		)
		self.assertHas(resp, 'This unit submission is pending review')
		self.assertHas(resp, '13♣')
		self.assertHas(resp, '3.7♥')

		# Check the updated problem set object
		pset = PSet.objects.get(student=alice, unit=unit1)
		self.assertEqual(pset.clubs, 13)
		self.assertEqual(pset.hours, 3.7)
		self.assertEqual(pset.feedback, 'hello')
		self.assertEqual(pset.special_notes, 'meow')
		self.assertEqual(os.path.basename(pset.upload.content.name), 'content2.txt')
		self.assertFalse(pset.accepted)
		self.assertFalse(pset.resubmitted)

		# Alice should still be Level 0 though
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 0')

		# simulate acceptance
		pset.status = 'A'
		pset.save()
		alice.unlocked_units.remove(unit1)
		alice.unlocked_units.add(unit2)
		alice.curriculum.set([unit1, unit2, unit3])

		# check it shows up this way
		resp = self.assertGet20X('pset', pset.pk)
		self.assertHas(resp, 'This unit submission was accepted')
		self.assertHas(resp, '13♣')
		self.assertHas(resp, '3.7♥')

		# Alice should show as leveled up now
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 4')

		# now let's say Alice resubmits
		content3 = StringIO('Rawr')
		content3.name = 'content3.txt'
		resp = self.assertPost20X(
			'resubmit-pset',
			alice.pk,
			data={
				'unit': unit1.pk,
				'clubs': 100,
				'hours': 20,
				'feedback': 'hello',
				'special_notes': 'meow',
				'content': content3,
				'next_unit_to_unlock': unit2.pk
			},
			follow=True
		)

		# check it shows up this way
		resp = self.assertGet20X('pset', pset.pk)
		self.assertHas(resp, 'This unit submission is pending review')
		self.assertHas(resp, '100♣')
		self.assertHas(resp, '20.0♥')

		# Check the problem set
		pset = PSet.objects.get(student=alice, unit=unit1)
		self.assertEqual(pset.clubs, 100)
		self.assertEqual(pset.hours, 20)
		self.assertEqual(pset.feedback, 'hello')
		self.assertEqual(pset.special_notes, 'meow')
		self.assertEqual(os.path.basename(pset.upload.content.name), 'content3.txt')
		self.assertFalse(pset.accepted)
		self.assertTrue(pset.resubmitted)

		# Alice is now back to Level 0
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 0')

		# simulate acceptance
		pset.status = 'A'
		pset.save()

		# Alice is now Level 14
		resp = self.assertGet20X('stats', alice.pk)
		self.assertHas(resp, 'Level 14')

		# check it shows up this way
		resp = self.assertGet20X('pset', pset.pk)
		self.assertHas(resp, 'This unit submission was accepted')
		self.assertHas(resp, '100♣')
		self.assertHas(resp, '20.0♥')

	def test_queryset(self):
		units = UnitFactory.create_batch(size=20)
		alice = StudentFactory.create()
		alice.curriculum.set(units[0:18])
		alice.unlocked_units.set(units[4:7])
		for unit in units[0:4]:
			PSetFactory.create(student=alice, unit=unit)
		PSetFactory.create(student=alice, unit=units[4], status='P')

		self.assertEqual(get_units_to_submit(alice).count(), 2)
		self.assertEqual(get_units_to_unlock(alice).count(), 11)


class TestPalace(EvanTestCase):
	def test_palace(self):
		alice = StudentFactory.create()
		self.login(alice)
		LevelFactory.reset_sequence()
		LevelFactory.create_batch(size=5)

		for i in range(0, 4):
			AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=2 * i + 1)
			self.assertNotHas(self.get('portal', alice.pk), 'Ruby palace')
			self.assertGet40X('palace-list', alice.pk, follow=True)
			self.assertGet40X('palace-update', alice.pk, follow=True)
			self.assertGet40X('diamond-update', alice.pk, follow=True)
		AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=9)
		self.assertHas(self.get('portal', alice.pk), 'Ruby palace')
		self.assertGetOK('palace-list', alice.pk)
		self.assertGetOK('palace-update', alice.pk)
		self.assertGetOK('diamond-update', alice.pk)
