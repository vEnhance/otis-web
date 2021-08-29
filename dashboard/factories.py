from core.factories import SemesterFactory, UnitFactory, UserFactory
from django.contrib.auth import get_user_model
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory, FileField, ImageField
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from otisweb.tests import UniqueFaker
from roster.factories import StudentFactory

from dashboard.models import Achievement, AchievementUnlock, Level, ProblemSuggestion, PSet, QuestComplete, SemesterDownloadFile, UploadedFile  # NOQA

User = get_user_model()


class UploadedFileFactory(DjangoModelFactory):
	class Meta:
		model = UploadedFile

	benefactor = SubFactory(StudentFactory)
	owner = LazyAttribute(lambda o: o.benefactor.user)
	category = 'psets'
	content = FileField(filename='pset.txt')
	unit = SubFactory(UnitFactory)


class SemesterDownloadFileFactory(DjangoModelFactory):
	class Meta:
		model = SemesterDownloadFile

	semester = SubFactory(SemesterFactory)
	content = FileField(filename='announcement.txt')


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

	student = SubFactory(StudentFactory)
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
	image = ImageField(filename='achievement_icon.png')
	description = UniqueFaker('sentence')


class LevelFactory(DjangoModelFactory):
	class Meta:
		model = Level

	threshold = Sequence(lambda n: n + 1)
	name = UniqueFaker('sentence')


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
