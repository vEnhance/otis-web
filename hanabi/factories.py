from core.factories import UserFactory
from evans_django_tools.testsuite import UniqueFaker
from factory.declarations import SubFactory
from factory.django import DjangoModelFactory

from hanabi.models import HanabiContest, HanabiPlayer


class HanabiContestFactory(DjangoModelFactory):
    class Meta:
        model = HanabiContest

    variant_name = "No Variant (5 Suits)"


class HanabiPlayerFactory(DjangoModelFactory):
    class Meta:
        model = HanabiPlayer

    user = SubFactory(UserFactory)
    hanab_username = UniqueFaker("slug")
