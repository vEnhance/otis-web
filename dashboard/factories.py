from core.factories import SemesterFactory, UnitFactory, UserFactory
from django.contrib.auth import get_user_model
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory, FileField, ImageField
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from otisweb.tests import UniqueFaker
from roster.factories import StudentFactory

User = get_user_model()


class UploadedFileFactory(DjangoModelFactory):
	benefactor = SubFactory(StudentFactory)
	owner = LazyAttribute(lambda o: o.benefactor.user)
	category = 'psets'
	content = FileField(filename='pset.txt')
	unit = SubFactory(UnitFactory)


class SemesterDownloadFileFactory(DjangoModelFactory):
	semester = SubFactory(SemesterFactory)
	content = FileField(filename='announcement.txt')


class PSetFactory(DjangoModelFactory):
	student = SubFactory(StudentFactory)
	unit = SubFactory(UnitFactory)
	upload = LazyAttribute(
		lambda o: UploadedFileFactory.create(benefactor=o.student, unit=o.unit)
	)
	next_unit_to_unlock = SubFactory(UnitFactory)


class ProblemSuggestionFactory(DjangoModelFactory):
	student = SubFactory(StudentFactory)
	unit = SubFactory(UnitFactory)
	weight = FuzzyChoice([2, 3, 5, 9])
	source = UniqueFaker('company')
	description = Faker('text')
	statement = Faker('sentence')
	solution = Faker('paragraph')


class AchievementFactory(DjangoModelFactory):
	code = UniqueFaker('bban')
	name = Faker('job')
	image = ImageField(filename='achievement_icon.png')
	description = UniqueFaker('sentence')


class LevelFactory(DjangoModelFactory):
	threshold = Sequence(lambda n: n + 1)
	name = Faker('job')


class AchievementUnlockFactory(DjangoModelFactory):
	user = SubFactory(UserFactory)
	achievement = SubFactory(AchievementFactory)
