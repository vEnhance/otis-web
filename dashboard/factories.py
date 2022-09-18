from core.factories import SemesterFactory, UnitFactory, UnitGroupFactory, UserFactory  # NOQA
from django.contrib.auth import get_user_model
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory, FileField, ImageField
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from otisweb.tests import UniqueFaker
from roster.factories import StudentFactory

from dashboard.models import Achievement, AchievementUnlock, BonusLevel, BonusLevelUnlock, Level, ProblemSuggestion, PSet, QuestComplete, SemesterDownloadFile, UploadedFile  # NOQA

User = get_user_model()


class UploadedFileFactory(DjangoModelFactory):
	class Meta:
		model = UploadedFile

	benefactor = SubFactory(StudentFactory)
	owner = LazyAttribute(lambda o: o.benefactor.user)
	category = 'psets'
	content = FileField(filename='UNIT_TESTING_pset.txt')
	unit = SubFactory(UnitFactory)


class SemesterDownloadFileFactory(DjangoModelFactory):
	class Meta:
		model = SemesterDownloadFile

	semester = SubFactory(SemesterFactory)
	content = FileField(filename='UNIT_TESTING_announcement.txt')


class PSetFactory(DjangoModelFactory):
	class Meta:
		model = PSet

	student = SubFactory(StudentFactory)
	unit = SubFactory(UnitFactory)
	upload = LazyAttribute(
		lambda o: UploadedFileFactory.create(benefactor=o.student, unit=o.unit)
	)
	next_unit_to_unlock = SubFactory(UnitFactory)
	approved = True


class ProblemSuggestionFactory(DjangoModelFactory):
	class Meta:
		model = ProblemSuggestion

	user = SubFactory(UserFactory)
	unit = SubFactory(UnitFactory)
	weight = FuzzyChoice([2, 3, 5, 9])
	source = UniqueFaker('company')
	description = Faker('text')
	statement = Faker('sentence')
	solution = Faker('paragraph')


class AchievementFactory(DjangoModelFactory):
	class Meta:
		model = Achievement

	code = UniqueFaker('bban')
	name = Faker('job')
	image = ImageField(filename='UNIT_TESTING_achievement_icon.png')
	description = UniqueFaker('sentence')


class LevelFactory(DjangoModelFactory):
	class Meta:
		model = Level

	threshold = Sequence(lambda n: n + 1)
	name = LazyAttribute(lambda o: f'Level {o.threshold}')


class AchievementUnlockFactory(DjangoModelFactory):
	class Meta:
		model = AchievementUnlock

	user = SubFactory(UserFactory)
	achievement = SubFactory(AchievementFactory)


class QuestCompleteFactory(DjangoModelFactory):
	class Meta:
		model = QuestComplete

	student = SubFactory(StudentFactory)
	title = Faker('job')
	spades = FuzzyChoice(list(range(1, 10)))


class BonusLevelFactory(DjangoModelFactory):
	class Meta:
		model = BonusLevel

	level = 100
	group = SubFactory(UnitGroupFactory)


class BonusLevelUnlockFactory(DjangoModelFactory):
	class Meta:
		model = BonusLevelUnlock

	student = SubFactory(StudentFactory)
	level = SubFactory(BonusLevelFactory)
