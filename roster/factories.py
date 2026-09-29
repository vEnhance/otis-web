from collections.abc import Sequence
from typing import Any

from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice, FuzzyInteger
from factory.helpers import post_generation

from core.factories import SemesterFactory, UnitFactory, UserFactory
from roster.models import (
    ApplyUUID,
    Assistant,
    AssistantListing,
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    StudentStanding,
    UnitPetition,
)


class ApplyUUIDFactory(DjangoModelFactory):
    class Meta:
        model = ApplyUUID

    uuid = Faker("uuid4")


class AssistantFactory(DjangoModelFactory):
    class Meta:
        model = Assistant

    user = SubFactory(UserFactory, is_staff=True)
    shortname = LazyAttribute(lambda o: o.user.first_name)


class AssistantListingFactory(DjangoModelFactory):
    class Meta:
        model = AssistantListing

    assistant = SubFactory(AssistantFactory)
    enabled = True
    offers_one_on_one = True
    time_zone = Faker("timezone")
    availability = "weekend evenings"
    next_steps = "Email me with your AoPS username."
    blurb = Faker("paragraph")


class RegistrationContainerFactory(DjangoModelFactory):
    class Meta:
        model = RegistrationContainer

    semester = SubFactory(SemesterFactory)


class StudentRegistrationFactory(DjangoModelFactory):
    class Meta:
        model = StudentRegistration

    user = SubFactory(UserFactory)
    container = SubFactory(RegistrationContainerFactory)
    parent_email = Faker("ascii_safe_email")
    gender = FuzzyChoice(("M", "F", "H"))
    graduation_year = FuzzyInteger(2021, 2029)
    school_name = Faker("city")


class StudentFactory(DjangoModelFactory):
    class Meta:
        model = Student
        skip_postgeneration_save = True

    user = SubFactory(UserFactory)
    semester = SubFactory(SemesterFactory)
    standing = StudentStanding.GOOD
    last_level_seen = 0

    @post_generation
    def assistants(
        self, create: bool, extracted: Sequence[Assistant] | None, **kwargs: Any
    ):
        if create and extracted:
            student: Student = self  # type: ignore
            student.assistants.set(extracted)


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    student = SubFactory(StudentFactory)
    preps_taught = 2


class UnitPetitionFactory(DjangoModelFactory):
    class Meta:
        model = UnitPetition

    student = SubFactory(StudentFactory)
    unit = SubFactory(UnitFactory)
    action_type = "PET_ACT_UNLOCK"
    explanation = Faker("sentence")
