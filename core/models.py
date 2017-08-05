from __future__ import unicode_literals

from django.db import models
from positions import PositionField

# Create your models here.

class Semester(models.Model):
	"""Represents an academic semester, e.g. "Fall 2017"."""
	name = models.CharField(max_length=255,
			help_text = "Text description such as 'Fall 2017'", unique=True)
	active = models.BooleanField(default=False,
			help_text = "Whether the semester is currently active "
			"(there should thus be at most one active semester)")
	def __unicode__(self):
		return self.name

class Handout(models.Model):
	"""Represents a PDF of a unit, with problems and solutions"""
	name = models.CharField(max_length=255,
			help_text = "The display name for the handout, like 'Weird Geo'")
	code = models.CharField(max_length=255,
			help_text = "The version code for the handout, like 'ZGX'")
	prob_url = models.CharField(max_length=255,
			help_text = "The URL for the problems handout",
			blank = True)
	soln_url = models.CharField(max_length=255,
			help_text = "The URL for the solutions handout",
			blank = True)
	position = PositionField(
			help_text="The ordering of the relative handouts to each other.")
	def __unicode__(self):
		return self.name + u" [" + self.code + u"]"
	class Meta:
		unique_together = ('name', 'code')
