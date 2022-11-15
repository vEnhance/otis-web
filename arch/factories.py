from evans_django_tools.testsuite import UniqueFaker
from factory.declarations import Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from .models import Hint, Problem


class ProblemFactory(DjangoModelFactory):

    class Meta:
        model = Problem

    puid = UniqueFaker('pystr')


class HintFactory(DjangoModelFactory):

    class Meta:
        model = Hint

    problem = SubFactory(ProblemFactory)
    number = Sequence(lambda n: n)
    keywords = Faker('job')
    content = Faker('sentence')
