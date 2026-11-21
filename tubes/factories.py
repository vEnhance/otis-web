from datetime import timedelta

from django.utils import timezone
from factory.declarations import LazyFunction, SubFactory, Trait
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice, FuzzyInteger

from core.factories import UserFactory

from .models import (
    JoinRecord,
    OIMEComment,
    OIMEContributor,
    OIMEFight,
    OIMEProposal,
    OIMESelection,
    OIMEYear,
    Tube,
)


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

    tube = SubFactory(TubeFactory)
    user = None
    activation_time = None
    invite_url = Faker("url")


class OIMEContributorFactory(DjangoModelFactory):
    class Meta:
        model = OIMEContributor

    user = SubFactory(UserFactory)
    display_name = Faker("name")


class OIMEProposalFactory(DjangoModelFactory):
    class Meta:
        model = OIMEProposal

    author = SubFactory(OIMEContributorFactory)
    title = Faker("sentence", nb_words=4)
    statement = Faker("paragraph")
    answer = FuzzyInteger(0, 999)
    solution = Faker("paragraph")
    subject = FuzzyChoice(["A", "C", "G", "N"])
    difficulty = FuzzyInteger(1, 5)
    is_draft = False

    class Params:
        archived = Trait(archive_reason="OTHER")


class OIMEFightFactory(DjangoModelFactory):
    class Meta:
        model = OIMEFight

    contributor = SubFactory(OIMEContributorFactory)
    proposal = SubFactory(OIMEProposalFactory)
    status = "OIME_TBD"
    wrong_answers = 0


class OIMECommentFactory(DjangoModelFactory):
    class Meta:
        model = OIMEComment

    author = SubFactory(OIMEContributorFactory)
    proposal = SubFactory(OIMEProposalFactory)
    content = Faker("paragraph")


class OIMEYearFactory(DjangoModelFactory):
    """A year whose proposal window is open right now and that is not released."""

    class Meta:
        model = OIMEYear

    display_name = Faker("company")
    proposals_open_at = LazyFunction(lambda: timezone.now() - timedelta(days=1))
    proposals_close_at = LazyFunction(lambda: timezone.now() + timedelta(days=30))
    release_at = None
    overleaf_url = Faker("url")


class OIMESelectionFactory(DjangoModelFactory):
    class Meta:
        model = OIMESelection

    year = SubFactory(OIMEYearFactory)
    proposal = SubFactory(OIMEProposalFactory)
    status = "SEL_SHORTLISTED"
    editor = None
