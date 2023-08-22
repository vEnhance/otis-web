from factory.django import DjangoModelFactory

from .models import OpalHunt

from django.utils.timezone import utc
from factory.faker import Faker

class OpalHuntFactory(DjangoModelFactory):
    class Meta:
        model = OpalHunt

    name = "Your Otis in April"
    start_date = Faker("past_datetime", tzinfo=utc)
