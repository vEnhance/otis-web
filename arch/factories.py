from factory.declarations import Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyInteger

from core.factories import UserFactory

from .models import Hint, Problem, Vote


class ProblemFactory(DjangoModelFactory):
    class Meta:
        model = Problem

    # TODO better way of all uppercase
    puid = Faker(
        "pystr_format", string_format="??????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )


class HintFactory(DjangoModelFactory):
    class Meta:
        model = Hint

    problem = SubFactory(ProblemFactory)
    number = Sequence(lambda n: n)
    keywords = Faker("job")
    content = Faker("sentence")


class VoteFactory(DjangoModelFactory):
    class Meta:
        model = Vote

    user = SubFactory(UserFactory)
    problem = SubFactory(ProblemFactory)
    niceness = FuzzyInteger(0, 10)
