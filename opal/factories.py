import datetime

from factory.django import DjangoModelFactory
from factory.faker import Faker

from .models import OpalHunt


class OpalHuntFactory(DjangoModelFactory):
    class Meta:
        model = OpalHunt

    name = "Your Otis in April"
    start_date = Faker("past_datetime", tzinfo=datetime.timezone.utc)
