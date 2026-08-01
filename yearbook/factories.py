from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice

from core.factories import UserFactory
from roster.country_abbrevs import COUNTRY_CHOICES

from .models import YearbookEntry


class YearbookEntryFactory(DjangoModelFactory):
    class Meta:
        model = YearbookEntry

    user = SubFactory(UserFactory)
    tagline = Faker("catch_phrase")
    country = FuzzyChoice([country[0] for country in COUNTRY_CHOICES])
    graduation_year = 2025
    university = Faker("company")
    bio = Faker("paragraph")
