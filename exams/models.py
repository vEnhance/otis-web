from __future__ import unicode_literals

from django.db import models
import roster.models

import string
import datetime

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
			return "Test " + str(self.number)
		else:
			return "Quiz " + string.ascii_uppercase[self.number-1]

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

class Quiz(models.Model):
	exam = models.OneToOneField(PracticeExam,
			on_delete = models.CASCADE,
			help_text = "The associated exam for this answer key")
	answer1 = models.IntegerField(help_text = "Answer to p1", default = 0)
	answer2 = models.IntegerField(help_text = "Answer to p2", default = 0)
	answer3 = models.IntegerField(help_text = "Answer to p3", default = 0)
	answer4 = models.IntegerField(help_text = "Answer to p4", default = 0)
	answer5 = models.IntegerField(help_text = "Answer to p5", default = 0)

class ExamSubmission(models.Model):
	quiz = models.ForeignKey(Quiz,
			on_delete = models.CASCADE,
			help_text = "The quiz being submitted for")
	student = models.ForeignKey(roster.models.Student,
			on_delete = models.CASCADE,
			help_text = "The student taking the exam")
	guess1 = models.IntegerField(help_text = "Guess for p1", default = 0)
	guess2 = models.IntegerField(help_text = "Guess for p2", default = 0)
	guess3 = models.IntegerField(help_text = "Guess for p3", default = 0)
	guess4 = models.IntegerField(help_text = "Guess for p4", default = 0)
	guess5 = models.IntegerField(help_text = "Guess for p5", default = 0)
	submitted = models.DateTimeField(help_text = "When the quiz was submitted",
			auto_now_add = True)
	class Meta:
		unique_together = ('quiz', 'student',)
