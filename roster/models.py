from __future__ import unicode_literals

from django.db import models
from django.contrib.auth import models as auth
import core

# Create your models here.

class Assistant(models.Model):
	"""This is a pair of a user and a semester (with a display name).
	Currently don't need much information about them..."""
	# TODO: should we really allow user to be null?
	user = models.ForeignKey(auth.User, blank=True, null=True,
			help_text = "The Django Auth user attached to the Assistant")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this Assistant")
	name = models.CharField(max_length = 80,
			help_text = "The display name for this Assistant (e.g. a nickname)")
	def __unicode__(self):
		return self.name
	def student_count(self):
		return self.student_set.count()

class Student(models.Model):
	"""This is really a pair of a user and a semester (with a display name),
	endowed with the data of the curriculum of that student.
	It also names the assistant of the student, if any."""
	# TODO: should we really allow user to be null?
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
	def __unicode__(self):
		return self.name + " (" + unicode(self.semester) + ")"
	# TODO unique together: user + semester

	def is_taught_by(self, user):
		"""Checks whether the specified user is not the same as the student,
		but has permission to view and edit the student's files and so on.
		(This means the user is either an assistant for that student
		or has staff privileges.)"""
		return user.is_staff or (self.assistant.user == user)
	def can_view(self, user):
		"""Checks whether the specified user is either same as the student,
		or is an instructor for that student."""
		return self.user == user or self.is_taught_by(user)
