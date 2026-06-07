from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice, FuzzyInteger

from core.factories import UserFactory

from .models import JoinRecord, OIMEAttempt, OIMEComment, OIMEProposal, OIMESolverRole, Tube


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


class OIMEProposalFactory(DjangoModelFactory):
    class Meta:
        model = OIMEProposal

    author = SubFactory(UserFactory)
    statement = Faker("paragraph")
    answer = FuzzyInteger(0, 999)
    solution = Faker("paragraph")
    subject = FuzzyChoice(["A", "C", "G", "N"])
    difficulty = FuzzyInteger(1, 5)


class OIMESolverRoleFactory(DjangoModelFactory):
    class Meta:
        model = OIMESolverRole

    user = SubFactory(UserFactory)
    is_serious = False


class OIMEAttemptFactory(DjangoModelFactory):
    class Meta:
        model = OIMEAttempt

    user = SubFactory(UserFactory)
    proposal = SubFactory(OIMEProposalFactory)
    status = "IN_PROGRESS"
    wrong_answers = 0


class OIMECommentFactory(DjangoModelFactory):
    class Meta:
        model = OIMEComment

    author = SubFactory(UserFactory)
    proposal = SubFactory(OIMEProposalFactory)
    content = Faker("paragraph")
