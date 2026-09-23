import datetime

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from core.factories import UserFactory

from .models import PonziInvestment, PonziScheme


class PonziSchemeFactory(DjangoModelFactory):
    class Meta:
        model = PonziScheme

    title = Faker("bs")
    start_date = Faker("past_datetime", tzinfo=datetime.UTC)


class PonziInvestmentFactory(DjangoModelFactory):
    class Meta:
        model = PonziInvestment

    scheme = SubFactory(PonziSchemeFactory)
    user = SubFactory(UserFactory)
    amount = 10
