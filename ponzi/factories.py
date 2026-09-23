import datetime

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from core.factories import SemesterFactory
from roster.factories import StudentFactory

from .models import PonziInvestment, PonziScheme


class PonziSchemeFactory(DjangoModelFactory):
    class Meta:
        model = PonziScheme

    semester = SubFactory(SemesterFactory)
    title = Faker("bs")
    start_date = Faker("past_datetime", tzinfo=datetime.UTC)


class PonziInvestmentFactory(DjangoModelFactory):
    class Meta:
        model = PonziInvestment

    scheme = SubFactory(PonziSchemeFactory)
    student = SubFactory(StudentFactory)
    amount = 10
