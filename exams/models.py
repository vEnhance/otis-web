from __future__ import unicode_literals

import datetime
import string

import roster.models
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator, validate_comma_separated_integer_list  # NOQA
from django.db import models
from django.urls.base import reverse_lazy

# Create your models here.

exam_ans_validators = [validate_comma_separated_integer_list,]
class PracticeExam(models.Model):
	family = models.CharField(max_length = 10,
			choices = (("Waltz", "Waltz"), ("Foxtrot", "Foxtrot"),),
			help_text = "The family that the exam comes from.")
	is_test = models.BooleanField(help_text = "Whether this is a quiz or test")
	number = models.PositiveSmallIntegerField(
			help_text = "The number of the assignment (e.g. Test 8, Quiz D) ")
	def __str__(self):
		if self.is_test:
			return self.family + " Test " + self.get_number_display()
		else:
			return self.family + " Quiz " + self.get_number_display()

	# For quizzes only
	answer1 = models.CharField(max_length = 64,
			validators = exam_ans_validators, blank = True)
	answer2 = models.CharField(max_length = 64,
			validators = exam_ans_validators, blank = True)
	answer3 = models.CharField(max_length = 64,
			validators = exam_ans_validators, blank = True)
	answer4 = models.CharField(max_length = 64,
			validators = exam_ans_validators, blank = True)
	answer5 = models.CharField(max_length = 64,
			validators = exam_ans_validators, blank = True)
	url1 = models.CharField(max_length = 128, blank=True,
			validators = [URLValidator(),])
	url2 = models.CharField(max_length = 128, blank=True,
			validators = [URLValidator(),])
	url3 = models.CharField(max_length = 128, blank=True,
			validators = [URLValidator(),])
	url4 = models.CharField(max_length = 128, blank=True,
			validators = [URLValidator(),])
	url5 = models.CharField(max_length = 128, blank=True,
			validators = [URLValidator(),])

	start_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment opens.")
	due_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment should be due.")
	class Meta:
		ordering = ('family', '-is_test', 'number')
		unique_together = ('family', 'is_test', 'number')

	@property
	def pdfname(self):
		kind = 'Exam' if self.is_test else 'Quiz'
		return f'{kind}-{self.family}-{self.get_number_display()}.pdf'

	def get_number_display(self) -> str:
		if self.is_test:
			return f'{self.number:02d}'
		else:
			return string.ascii_uppercase[self.number-1]


	@property
	def overdue(self):
		return (self.due_date is not None) and (self.due_date < datetime.date.today())
	@property
	def started(self):
		if self.start_date is None: return True
		return (self.start_date <= datetime.date.today())
	@property
	def current(self):
		return self.started and not self.overdue

student_answer_validators = [
		MinValueValidator(-10**9), MaxValueValidator(10**9),
		]

class ExamAttempt(models.Model):
	quiz = models.ForeignKey(PracticeExam,
			on_delete = models.CASCADE,
			help_text = "The quiz being submitted for")
	score = models.SmallIntegerField(null = True, blank = True,
			help_text = "The number of correct answers")
	student = models.ForeignKey(roster.models.Student,
			on_delete = models.CASCADE,
			help_text = "The student taking the exam")
	guess1 = models.IntegerField(verbose_name = "Problem 1 response",
			blank = True, null = True, validators = student_answer_validators)
	guess2 = models.IntegerField(verbose_name = "Problem 2 response",
			blank = True, null = True, validators = student_answer_validators)
	guess3 = models.IntegerField(verbose_name = "Problem 3 response",
			blank = True, null = True, validators = student_answer_validators)
	guess4 = models.IntegerField(verbose_name = "Problem 4 response",
			blank = True, null = True, validators = student_answer_validators)
	guess5 = models.IntegerField(verbose_name = "Problem 5 response",
			blank = True, null = True, validators = student_answer_validators)
	submit_time = models.DateTimeField(help_text = "When the quiz was submitted",
			auto_now_add = True)
	class Meta:
		unique_together = ('quiz', 'student',)
	def __str__(self) -> str:
		return f'{self.student} tries {self.quiz}'
	def get_absolute_url(self) -> str:
		return reverse_lazy('show-exam', args=(self.student.pk, self.quiz.pk))
