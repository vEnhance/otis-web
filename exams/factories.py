from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.helpers import post_generation

from core.utils import storage_hash
from exams.models import ExamAttempt, PracticeExam
from roster.factories import StudentFactory


class TestFactory(DjangoModelFactory):
    class Meta:
        model = PracticeExam

    family = "Waltz"
    number = Sequence(lambda n: n + 1)
    is_test = True

    @post_generation
    def write_mock_media(self, create: bool, extracted: bool, **kwargs: dict[str, Any]):
        assert settings.TESTING is True
        if settings.TESTING_NEEDS_MOCK_MEDIA is False:
            return

        exam: PracticeExam = self  # type: ignore
        default_storage.save(
            "pdfs/" + storage_hash(exam.pdfname) + ".pdf", ContentFile(b"exam")
        )


class QuizFactory(TestFactory):
    is_test = False
    answer1 = Faker("random_number", digits=3)
    answer2 = Faker("random_number", digits=3)
    answer3 = Faker("random_number", digits=3)
    answer4 = Faker("random_number", digits=3)
    answer5 = Faker("random_number", digits=3)

    url1 = "http://example.com/1/"
    url2 = "http://example.com/2/"
    url3 = "http://example.com/3/"
    url4 = "http://example.com/4/"
    url5 = "http://example.com/5/"


class ExamAttemptFactory(DjangoModelFactory):
    class Meta:
        model = ExamAttempt

    student = SubFactory(StudentFactory)
    quiz = SubFactory(QuizFactory)
    score = 0

    guess1 = LazyAttribute(lambda o: o.quiz.answer1)
    guess2 = LazyAttribute(lambda o: o.quiz.answer2)
    guess3 = LazyAttribute(lambda o: o.quiz.answer3)
    guess4 = LazyAttribute(lambda o: o.quiz.answer4)
    guess5 = LazyAttribute(lambda o: o.quiz.answer5)
