from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from roster.factories import StudentFactory

from exams.models import ExamAttempt, PracticeExam


class ExamFactory(DjangoModelFactory):
	class Meta:
		model = PracticeExam

	family = 'Waltz'
	number = Sequence(lambda n: n + 1)
	is_test = False


class ExamAttemptFactory(DjangoModelFactory):
	class Meta:
		model = ExamAttempt

	student = SubFactory(StudentFactory)
	quiz = SubFactory(ExamFactory)
	score = 0

	guess1 = LazyAttribute(lambda o: o.quiz.answer1)
	guess2 = LazyAttribute(lambda o: o.quiz.answer2)
	guess3 = LazyAttribute(lambda o: o.quiz.answer3)
	guess4 = LazyAttribute(lambda o: o.quiz.answer4)
	guess5 = LazyAttribute(lambda o: o.quiz.answer5)
