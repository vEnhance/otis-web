from __future__ import unicode_literals

from django.db import models
from positions import PositionField

# Create your models here.

class Semester(models.Model):
	"""Represents an academic semester/year/etc, e.g. "Fall 2017"
	or "Year III"."""
	name = models.CharField(max_length=255,
			help_text = "Text description such as 'Year III'", unique=True)
	active = models.BooleanField(default=False,
			help_text = "Whether the semester is currently active "
			"(there should thus be at most one active semester).")
	registration_open = models.BooleanField(default=False,
			help_text = "Whether students can register for this semester yet.")
	exam_family = models.CharField(max_length = 10,
			choices = (("Waltz", "Waltz"), ("Foxtrot", "Foxtrot"), ("", "--"),),
			default = "",
			help_text = "The family of practice exams to display.")

	show_invoices = models.BooleanField(default=False,
			help_text = "Whether to display invoices for this semester.")
	prep_rate = models.PositiveSmallIntegerField(default=240,
			help_text = "The prep rate for the semester.")
	hour_rate = models.PositiveSmallIntegerField(default=80,
			help_text = "The hourly rate for the semester.")

	gradescope_key = models.CharField(max_length=10, blank=True,
			help_text = "The entry code for GradeScope this semester.")
	zoom_room_url = models.CharField(max_length=128, blank=True,
			help_text = "The entry point for the Zoom meeting room.")
	social_url = models.CharField(max_length=128, blank=True,
			help_text = "The link to social platform for this year.")

	calendar_url_meets_evan = models.TextField(blank=True,
			help_text = "Link to calendar for students with meetings with Evan")
	calendar_url_no_meets_evan = models.TextField(blank=True,
			help_text = "Link to calendar for students without meetings with Evan")

	def __str__(self):
		return self.name

class UnitGroup(models.Model):
	"""Represents an entire group of units with the same name,
	differing only in difficulty and version"""
	name = models.CharField(max_length=255, unique=True,
			help_text = "The display name for the handout, like 'Weird Geo'")
	description = models.TextField(help_text = "A description of what this unit is",
			blank = True)
	SUBJECT_CHOICES = (
			("A", "Algebra (Hufflepuff)"),
			("C", "Combinatorics (Gryffindor)"),
			("G", "Geometry (Slytherin)"),
			("N", "Number Theory (Ravenclaw)"),
			("F", "Functional Equations"),
			("M", "Miscellaneous"),
			)
	subject = models.CharField(max_length=2, choices = SUBJECT_CHOICES,
			help_text = "The subject for the unit")
	def __str__(self):
		return self.name
	class Meta:
		ordering = ('name',)

class Unit(models.Model):
	"""Represents a PDF of a unit, with problems and solutions"""
	group = models.ForeignKey(UnitGroup, null=True,
			on_delete = models.CASCADE,
			help_text = "The group that this unit belongs to")
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
	def __str__(self):
		if self.group is not None:
			return self.group.name + " [" + self.code + "]"
		return "-" + " [" + self.code + "]"
	class Meta:
		unique_together = ('group', 'code')
		ordering = ('position',)
	@property
	def list_display_position(self):
		return self.position
