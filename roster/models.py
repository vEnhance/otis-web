from __future__ import unicode_literals

from django.db import models
from django.contrib.auth import models as auth
import core

class Assistant(models.Model):
	"""This is a pair of a user and a semester (with a display name).
	Currently don't need much information about them..."""
	user = models.ForeignKey(auth.User, blank=True, null=True,
			help_text = "The Django Auth user attached to the Assistant")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this Assistant")
	name = models.CharField(max_length = 80,
			help_text = "The display name for this Assistant (e.g. a nickname)")
	def __str__(self):
		return self.name
	def student_count(self):
		return self.student_set.count()
	class Meta:
		unique_together = ('user', 'semester',)
		ordering = ('name',)

class Student(models.Model):
	"""This is really a pair of a user and a semester (with a display name),
	endowed with the data of the curriculum of that student.
	It also names the assistant of the student, if any."""
	user = models.ForeignKey(auth.User, blank=True, null=True,
			help_text = "The Django Auth user attached to the student")
	name = models.CharField(max_length = 80,
			help_text = "The display name for this student (e.g. a nickname)")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this student")
	curriculum = models.ManyToManyField(core.models.Unit, blank = True,
			help_text = "The choice of units that this student will work on")
	assistant = models.ForeignKey(Assistant, blank = True, null = True,
			help_text = "The Assistant for this student, if any")
	current_unit_index = models.SmallIntegerField(default = 0,
			help_text = "If this is equal to k, "
			"then the student has completed the first k units of his/her "
			"curriculum and is working on the (k+1)st unit")
	legit = models.BooleanField(default = True,
			help_text = "Whether this student is real. "
			"Set to false for dummy accounts and the like. "
			"This will hide them from the master schedule, for example.")
	def __str__(self):
		return self.name + " (" + str(self.semester) + ")"

	def is_taught_by(self, user):
		"""Checks whether the specified user is not the same as the student,
		but has permission to view and edit the student's files and so on.
		(This means the user is either an assistant for that student
		or has staff privileges.)"""
		return user.is_staff or (self.assistant is not None and self.assistant.user == user)
	def can_view_by(self, user):
		"""Checks whether the specified user is either same as the student,
		or is an instructor for that student."""
		return self.user == user or self.is_taught_by(user)
	class Meta:
		unique_together = ('user', 'semester',)
		ordering = ('name',)

	@property
	def curriculum_length(self):
		return self.curriculum.count()


PREP_RATE = 400 # 400 per semester...
HOUR_RATE = 80  # plus 80 per hour

class Invoice(models.Model):
	"""Billing information object for students."""

	student = models.OneToOneField(Student,
			help_text = "The invoice that this student is for.")
	preps_taught = models.SmallIntegerField(default = 0,
			help_text = "Number of semesters that development/preparation "
			"costs are charged.")
	hours_taught = models.DecimalField(max_digits = 8,
			decimal_places = 2, default = 0,
			help_text = "Number of hours taught for.")
	amount_owed = models.DecimalField(max_digits = 8,
			decimal_places = 2, null = True, blank = True,
			help_text = "Amount currently owed.")
	updated_at = models.DateTimeField(auto_now=True)

	@property
	def total_cost(self):
		return PREP_RATE*self.preps_taught + HOUR_RATE*self.hours_taught

	@property
	def total_owed(self):
		if self.amount_owed is None:
			return self.total_cost
		else:
			return self.amount_owed

	@property
	def cleared(self):
		"""Whether or not the student owes anything"""
		return (self.total_owed <= 0)

	@property
	def total_paid(self):
		if self.amount_owed is None:
			return 0
		else:
			return self.total_cost - self.amount_owed
