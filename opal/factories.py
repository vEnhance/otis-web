import datetime

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from core.factories import UserFactory
from evans_django_tools.testsuite import UniqueFaker

from .models import OpalAttempt, OpalHunt, OpalPuzzle


class OpalHuntFactory(DjangoModelFactory):
    class Meta:
        model = OpalHunt

    name = "Your Otis in April"
    start_date = Faker("past_datetime", tzinfo=datetime.timezone.utc)


class OpalPuzzleFactory(DjangoModelFactory):
    class Meta:
        model = OpalPuzzle

    hunt = SubFactory(OpalHuntFactory)
    slug = UniqueFaker("slug")
    title = Faker("company")
    answer = Faker("company")


class OpalAttemptFactory(DjangoModelFactory):
    class Meta:
        model = OpalAttempt

    puzzle = SubFactory(OpalPuzzleFactory)
    user = SubFactory(UserFactory)
    guess = Faker("company")
