from factory.django import DjangoModelFactory

from .models import OpalHunt


class OpalHuntFactory(DjangoModelFactory):
    class Meta:
        model = OpalHunt

    name = "Your OTIS in April"
