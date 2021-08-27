from core.factories import SemesterFactory
from factory.declarations import Sequence, SubFactory
from factory.django import DjangoModelFactory

from exams.models import PracticeExam


class ExamFactory(DjangoModelFactory):
	class Meta:
		model = PracticeExam

	semester = SubFactory(SemesterFactory)
	number = Sequence(lambda n: n + 1)
	is_test = False
