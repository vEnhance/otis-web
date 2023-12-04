from factory.django import DjangoModelFactory
from factory.faker import Faker

from .models import Tube


class TubeFactory(DjangoModelFactory):
    class Meta:
        model = Tube

    display_name = Faker("company")
    description = Faker("paragraph")
    status = "TB_ACTIVE"
    main_url = Faker("url")
