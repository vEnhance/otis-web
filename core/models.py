from __future__ import unicode_literals

from datetime import datetime
from typing import Callable

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.manager import BaseManager
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from positions import PositionField

User = get_user_model()
# Create your models here.


class Semester(models.Model):
	"""Represents an academic semester/year/etc, e.g. "Fall 2017"
	or "Year III"."""
	name = models.CharField(
		max_length=255, help_text="Text description such as 'Year III'", unique=True
	)
	active = models.BooleanField(
		default=False,
		help_text="Whether the semester is currently active "
		"(there should thus be at most one active semester)."
	)
	exam_family = models.CharField(
		max_length=10,
		choices=(
			("Waltz", "Waltz"),
			("Foxtrot", "Foxtrot"),
			("", "--"),
		),
		default="",
		help_text="The family of practice exams to display."
	)
	uses_legacy_pset_system = models.BooleanField(
		help_text="Whether the pset uses the old system of upload checking", default=False
	)

	show_invoices = models.BooleanField(
		default=False, help_text="Whether to display invoices for this semester."
	)
	prep_rate = models.PositiveSmallIntegerField(
		default=240, help_text="The prep rate for the semester."
	)
	hour_rate = models.PositiveSmallIntegerField(
		default=80, help_text="The hourly rate for the semester."
	)
	first_payment_deadline = models.DateTimeField(
		null=True, blank=True, help_text="Deadline for nonzero payment."
	)
	most_payment_deadline = models.DateTimeField(
		null=True, blank=True, help_text="Deadline for two-thirds of the payment."
	)

	gradescope_key = models.CharField(
		max_length=10, blank=True, help_text="The entry code for GradeScope this semester."
	)
	social_url = models.CharField(
		max_length=128, blank=True, help_text="The link to social platform for this year."
	)

	calendar_url_meets_evan = models.TextField(
		blank=True, help_text="Link to calendar for students with meetings with Evan"
	)
	calendar_url_no_meets_evan = models.TextField(
		blank=True, help_text="Link to calendar for students without meetings with Evan"
	)

	def __str__(self) -> str:
		return self.name

	def get_absolute_url(self):
		return reverse_lazy("past", args=(self.pk, ))


class UnitGroup(models.Model):
	"""Represents an entire group of units with the same name,
	differing only in difficulty and version"""
	objects: BaseManager['UnitGroup']
	unit_set: BaseManager['Unit']
	get_subject_display: Callable[[], str]

	name = models.CharField(
		max_length=255, unique=True, help_text="The display name for the handout, like 'Weird Geo'"
	)
	slug = models.SlugField(
		max_length=80, help_text="The slug for the filename for this unit group", unique=True
	)
	description = models.TextField(help_text="A description of what this unit is", blank=True)
	SUBJECT_CHOICES = (
		("A", "Algebra (Hufflepuff)"),
		("C", "Combinatorics (Gryffindor)"),
		("G", "Geometry (Slytherin)"),
		("N", "Number Theory (Ravenclaw)"),
		("F", "Functional Equations"),
		("M", "Miscellaneous"),
		("K", "Null"),
	)
	subject = models.CharField(
		max_length=2, choices=SUBJECT_CHOICES, help_text="The subject for the unit"
	)
	hidden = models.BooleanField(
		help_text="Whether this unit is hidden from students", default=False
	)

	def __str__(self) -> str:
		return self.name

	@property
	def get_subject_short_display(self):
		if self.subject == "A":
			return "Algebra"
		elif self.subject == "C":
			return "Combo"
		elif self.subject == "G":
			return "Geom"
		elif self.subject == "N":
			return "Number theory"
		elif self.subject == "M":
			return "Misc"
		elif self.subject == "F":
			return "Func eqn"
		elif self.subject == "K":
			return "Secret"

	class Meta:
		ordering = ('name', )


class Unit(models.Model):
	"""Represents a PDF of a unit, with problems and solutions"""
	group = models.ForeignKey(
		UnitGroup,
		on_delete=models.CASCADE,
		help_text="The group that this unit belongs to",
	)
	code = models.CharField(
		max_length=255,
		help_text="The version code for the handout, like 'ZGX'",
	)
	position = PositionField(help_text="The ordering of the relative handouts to each other.")

	def __str__(self) -> str:
		if self.group is not None:
			return self.group.name + " [" + self.code + "]"
		return "-" + " [" + self.code + "]"

	class Meta:
		unique_together = ('group', 'code')
		ordering = ('position', )

	@property
	def list_display_position(self):
		return self.position

	@property
	def problems_pdf_filename(self) -> str:
		return self.code + '-' + self.group.slug + '.pdf'

	@property
	def solutions_pdf_filename(self) -> str:
		return self.code + '-sol-' + self.group.slug + '.pdf'

	@property
	def problems_tex_filename(self) -> str:
		return self.code + '-tex-' + self.group.slug + '.tex'

	def get_absolute_url(self):
		return reverse("view-problems", args=(self.pk, ))


class UserProfile(models.Model):
	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		help_text="The user these preferences belong to",
		related_name="profile",
	)

	show_bars = models.BooleanField(
		verbose_name="Level bars",
		help_text="Displays the level bars on the main portal",
		default=True
	)

	show_completed_by_default = models.BooleanField(
		verbose_name="Show completed",
		help_text="Displays completed units on the main portal by default",
		default=True
	)

	show_locked_by_default = models.BooleanField(
		verbose_name="Show locked",
		help_text="Displays locked units on the main portal by default",
		default=True
	)

	last_seen = models.DateTimeField(
		help_text="Last time user was seen at all",
		default=datetime.fromtimestamp(0, tz=timezone.utc),
	)
	last_email_dismiss = models.DateTimeField(
		help_text="Last time user dismissed the emails modal.",
		default=datetime.fromtimestamp(0, tz=timezone.utc),
	)
	last_download_dismiss = models.DateTimeField(
		help_text="Last time user dismissed the downloads modal.",
		default=datetime.fromtimestamp(0, tz=timezone.utc),
	)


	def __str__(self) -> str:
		return f"Prefs for {self.user.username}"
