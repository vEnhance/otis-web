from evans_django_tools.testsuite import UniqueFaker
from factory.django import DjangoModelFactory
from factory.declarations import SubFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from core.factories import UserFactory
from core.factories import UnitFactory

from .models import ProblemSuggestion


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
