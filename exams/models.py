from __future__ import unicode_literals

import datetime
import string

import roster.models
from django.db import models
from django.urls.base import reverse_lazy

# Create your models here.

class PracticeExam(models.Model):
	family = models.CharField(max_length = 10,
			choices = (("Waltz", "Waltz"), ("Foxtrot", "Foxtrot"),),
			help_text = "The family that the exam comes from.")
	is_test = models.BooleanField(help_text = "Whether this is a quiz or test")
	number = models.PositiveSmallIntegerField(
			help_text = "The number of the assignment (e.g. Test 8, Quiz D) ")
	pdf_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL for the external final for this exam.")
	def __str__(self):
		if self.is_test:
			return self.family + " Test " + str(self.number)
		else:
			return self.family + " Quiz " + string.ascii_uppercase[self.number-1]

	# For quizzes only
	answer1 = models.IntegerField(help_text = "Answer to p1",
			null = True, blank = True)
	answer2 = models.IntegerField(help_text = "Answer to p2",
			null = True, blank = True)
	answer3 = models.IntegerField(help_text = "Answer to p3",
			null = True, blank = True)
	answer4 = models.IntegerField(help_text = "Answer to p4",
			null = True, blank = True)
	answer5 = models.IntegerField(help_text = "Answer to p5",
			null = True, blank = True)

	start_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment opens.")
	due_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment should be due.")
	class Meta:
		ordering = ('family', '-is_test', 'number')
		unique_together = ('family', 'is_test', 'number')

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
	def get_absolute_url(self):
		# TODO fix
		return self.pdf_url or 'TODO'

class ExamAttempt(models.Model):
	quiz = models.ForeignKey(PracticeExam,
			on_delete = models.CASCADE,
			help_text = "The quiz being submitted for")
	student = models.ForeignKey(roster.models.Student,
			on_delete = models.CASCADE,
			help_text = "The student taking the exam")
	guess1 = models.IntegerField(verbose_name = "Problem 1 response",
			default = 0, blank = True, null = True)
	guess2 = models.IntegerField(verbose_name = "Problem 2 response",
			default = 0, blank = True, null = True)
	guess3 = models.IntegerField(verbose_name = "Problem 3 response",
			default = 0, blank = True, null = True)
	guess4 = models.IntegerField(verbose_name = "Problem 4 response",
			default = 0, blank = True, null = True)
	guess5 = models.IntegerField(verbose_name = "Problem 5 response",
			default = 0, blank = True, null = True)
	submit_time = models.DateTimeField(help_text = "When the quiz was submitted",
			auto_now_add = True)
	class Meta:
		unique_together = ('quiz', 'student',)
	def __str__(self) -> str:
		return f'{self.student} tries {self.quiz}'
	def get_absolute_url(self) -> str:
		return reverse_lazy('show-exam', args=(self.student.pk, self.quiz.pk))
