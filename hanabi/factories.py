import datetime

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyInteger

from core.factories import UserFactory
from otisweb_testsuite import UniqueFaker
from hanabi.models import HanabiContest, HanabiParticipation, HanabiPlayer, HanabiReplay


class HanabiContestFactory(DjangoModelFactory):
    class Meta:
        model = HanabiContest

    variant_id = 0
    variant_name = "No Variant (5 Suits)"
    start_date = Faker("past_datetime", tzinfo=datetime.timezone.utc)
    end_date = Faker("future_datetime", tzinfo=datetime.timezone.utc)


class HanabiPlayerFactory(DjangoModelFactory):
    class Meta:
        model = HanabiPlayer

    user = SubFactory(UserFactory)
    hanab_username = UniqueFaker("slug")


class HanabiReplayFactory(DjangoModelFactory):
    class Meta:
        model = HanabiReplay

    contest = SubFactory(HanabiContestFactory)
    replay_id = UniqueFaker("random_number", digits=8)
    game_score = FuzzyInteger(10, 15)
    turn_count = FuzzyInteger(10, 50)


class HanabiParticipationFactory(DjangoModelFactory):
    class Meta:
        model = HanabiParticipation

    player = SubFactory(HanabiPlayerFactory)
    replay = SubFactory(HanabiReplayFactory)
