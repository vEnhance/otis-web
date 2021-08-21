import random

from django.contrib.auth import get_user_model
from django.utils.text import slugify
from factory import Faker, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from otisweb.tests import UniqueFaker

from core.models import Semester, Unit, UnitGroup

User = get_user_model()


class UserFactory(DjangoModelFactory):
	class Meta:
		model = User

	first_name = Faker('first_name_female')
	last_name = Faker('last_name_female')
	username = UniqueFaker('user_name')
	email = Faker('ascii_safe_email')


class UnitGroupFactory(DjangoModelFactory):
	class Meta:
		model = UnitGroup

	name = Faker('job')
	slug = LazyAttribute(lambda o: slugify(o.name))
	description = Faker('catch_phrase')
	subject = FuzzyChoice(UnitGroup.SUBJECT_CHOICES)


class UnitFactory(DjangoModelFactory):
	class Meta:
		model = Unit

	code = LazyAttribute(
		lambda o: random.choice('BDZ') + o.group.subject[0] + random.choice('WXY')
	)
	group = SubFactory(UnitGroupFactory)
	position = Sequence(lambda n: n + 1)


class SemesterFactory(DjangoModelFactory):
	class Meta:
		model = Semester

	name = Sequence(lambda n: f"Year {n + 1}")
	active = True
	exam_family = 'Waltz'
