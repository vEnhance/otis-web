from django.utils.timezone import utc
from factory.declarations import PostGenerationMethodCall, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyDecimal

from core.factories import SemesterFactory, UserFactory
from evans_django_tools.testsuite import UniqueFaker

from .models import Guess, Market


class MarketFactory(DjangoModelFactory):
    class Meta:
        model = Market

    semester = SubFactory(SemesterFactory)
    start_date = Faker("past_datetime", tzinfo=utc)
    end_date = Faker("future_datetime", tzinfo=utc)

    slug = UniqueFaker("slug")
    title = Faker("bs")
    prompt = Faker("paragraph")


class GuessFactory(DjangoModelFactory):
    class Meta:
        model = Guess

    user = SubFactory(UserFactory)
    market = SubFactory(MarketFactory)
    value = FuzzyDecimal(1, 10000)

    postgen_set_score = PostGenerationMethodCall("set_score")
