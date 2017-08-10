from __future__ import unicode_literals

import core
from django.db import models

# Create your models here.

class MockOlympiad(models.Model):
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
	solns_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the solutions")
	due_date = models.DateField(null = True, blank = True,
			help_text = "When the assignment should be due. Leave blank if not active this semester.")
	def __unicode__(self):
		return self.family + " " + unicode(self.number)
	@property
	def active(self):
		return (self.due_date is not None)
	class Meta:
		unique_together = ('family', 'number')

class Assignment(models.Model):
	"""An assignment which is just a text description (e.g. HMMT practices)."""
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester that the assignment is given in")
	name = models.CharField(max_length = 80,
			help_text = "Name / description of the assignment")
	due_date = models.DateField(help_text = "When the assignment is due")
	def __unicode__(self):
		return self.name
	class Meta:
		unique_together = ('semester', 'name')
