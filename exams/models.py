from __future__ import unicode_literals

import core
import datetime
from django.db import models

# Create your models here.

class AbstractAssignmentModel(models.Model):
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

	start_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment opens. Leave blank if not active this semester.")
	due_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment should be due. Leave blank if not active this semester.")

	class Meta:
		abstract = True

class MockOlympiad(AbstractAssignmentModel):
	"""An assignment which is a mock olympiad (i.e. Waltz, Tango, Foxtrot)."""
	CHOICES = ((_, _) for _ in ("Waltz", "Tango", "Foxtrot"))
	family = models.CharField(max_length = 10, choices = CHOICES,
			help_text = "The family that the mock olympiad comes from")
	number = models.PositiveSmallIntegerField(
			help_text = "The number of the test (e.g. Waltz 8)")
	jmo_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the JMO problems")
	usamo_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the USAMO problems")
	soln_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the solutions")

	def __str__(self):
		return self.family + " " + str(self.number)
	class Meta:
		unique_together = ('family', 'number')
		ordering = ('due_date', 'start_date', 'family', 'number')

class Assignment(AbstractAssignmentModel):
	"""An assignment which is just a text description (e.g. HMMT practices)."""
	name = models.CharField(max_length = 80, unique = True,
			help_text = "Name / description of the assignment")
	start_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment opens. Leave blank if not active this semester.")
	due_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment is due. Leave blank if not active this semester.")
	def __str__(self):
		return self.name
	class Meta:
		ordering = ('due_date', 'start_date', 'name')
