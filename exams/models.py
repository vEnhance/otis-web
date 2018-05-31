from __future__ import unicode_literals

import core
from django.db import models

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
		ordering = ('family', 'is_test', 'number')
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
