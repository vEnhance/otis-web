from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from factory import post_generation
from factory.declarations import Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyInteger

from core.factories import UserFactory
from core.utils import storage_hash

from .models import Hint, Problem, Vote


class ProblemFactory(DjangoModelFactory):
    class Meta:
        model = Problem

    # TODO better way of all uppercase
    puid = Faker(
        "pystr_format", string_format="??????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )

    @post_generation
    def write_mock_media(self, create: bool, extracted: bool, **kwargs: dict[str, Any]):
        assert settings.TESTING is True
        if settings.TESTING_NEEDS_MOCK_MEDIA is False:
            return
        problem: Problem = self  # type: ignore
        filename = problem.puid + ".tex"
        default_storage.save(
            "protected/" + storage_hash(filename) + ".tex",
            ContentFile(b"hi i'm a solution"),
        )


class HintFactory(DjangoModelFactory):
    class Meta:
        model = Hint

    problem = SubFactory(ProblemFactory)
    number = Sequence(lambda n: n)
    keywords = Faker("job")
    content = Faker("sentence")


class VoteFactory(DjangoModelFactory):
    class Meta:
        model = Vote

    user = SubFactory(UserFactory)
    problem = SubFactory(ProblemFactory)
    niceness = FuzzyInteger(0, 10)
