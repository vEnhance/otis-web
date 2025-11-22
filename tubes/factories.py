import factory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from .models import JoinRecord, Tube


class TubeFactory(DjangoModelFactory):
    class Meta:
        model = Tube

    display_name = Faker("company")
    description = Faker("paragraph")
    status = "TB_ACTIVE"
    main_url = Faker("url")


class JoinRecordFactory(DjangoModelFactory):
    class Meta:
        model = JoinRecord

    tube = factory.SubFactory(TubeFactory)
    user = None
    activation_time = None
    invite_url = Faker("url")
