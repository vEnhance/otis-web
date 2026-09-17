import datetime

from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from core.factories import SemesterFactory
from roster.factories import AssistantFactory, StudentFactory

from .models import GMFeedback, InstructorComment, Survey, SurveyCompletion


class SurveyFactory(DjangoModelFactory):
    class Meta:
        model = Survey

    semester = SubFactory(SemesterFactory)
    name = Faker("catch_phrase")
    opens_at = Faker("past_datetime", tzinfo=datetime.UTC)
    closes_at = Faker("future_datetime", tzinfo=datetime.UTC)
    essay_prompt = Faker("sentence")
    instructor_comments_prompt = Faker("sentence")
    satisfaction_prompt = Faker("sentence")
    anything_else_prompt = Faker("sentence")


class SurveyCompletionFactory(DjangoModelFactory):
    class Meta:
        model = SurveyCompletion

    survey = SubFactory(SurveyFactory)
    student = SubFactory(
        StudentFactory,
        semester=LazyAttribute(lambda o: o.factory_parent.survey.semester),
    )


class GMFeedbackFactory(DjangoModelFactory):
    class Meta:
        model = GMFeedback

    survey = SubFactory(SurveyFactory)
    essay = Faker("paragraph")


class InstructorCommentFactory(DjangoModelFactory):
    class Meta:
        model = InstructorComment

    survey = SubFactory(SurveyFactory)
    assistant = SubFactory(AssistantFactory)
    comments = Faker("paragraph")
