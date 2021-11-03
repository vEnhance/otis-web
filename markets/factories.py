from core.factories import SemesterFactory, UserFactory
from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyDecimal
from otisweb.tests import UniqueFaker

from .models import Guess, Market


class MarketFactory(DjangoModelFactory):
	class Meta:
		model = Market

	semester = SubFactory(SemesterFactory)
	start_date = Faker('past_datetime')
	end_date = Faker('future_datetime')

	slug = UniqueFaker('slug')
	title = Faker('bs')
	prompt = Faker('paragraph')


class GuessFactory(DjangoModelFactory):
	class Meta:
		model = Guess

	user = SubFactory(UserFactory)
	market = SubFactory(MarketFactory)
	value = FuzzyDecimal(1, 10000)
	score = LazyAttribute(lambda o: o.get_score())
