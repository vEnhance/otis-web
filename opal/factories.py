from django.utils.timezone import utc
from factory.django import DjangoModelFactory
from factory.faker import Faker

from .models import OpalHunt


class OpalHuntFactory(DjangoModelFactory):
    class Meta:
        model = OpalHunt

    name = "Your Otis in April"
    start_date = Faker("past_datetime", tzinfo=utc)
