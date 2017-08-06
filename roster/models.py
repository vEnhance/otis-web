from __future__ import unicode_literals

from django.db import models
from django.contrib.auth import models as auth
import core

# Create your models here.

class TA(models.Model):
	"""This is a single user with the data of the students they're assisting."""
	user = models.ForeignKey(auth.User,
			help_text = "The Django Auth user attached to the TA")
	def __unicode__(self):
		return unicode(self.user)
	def student_count(self):
		return self.student_set.count()

class Student(models.Model):
	"""This is really a pair of a user and a semester,
	endowed with the data of the curriculum of that student."""
	user = models.ForeignKey(auth.User,
			help_text = "The Django Auth user attached to the student")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this student")
	curriculum = models.ManyToManyField(core.models.Unit,
			help_text = "The choice of units that this student will work on")
	assistant = models.ForeignKey(TA, blank = True, null = True,
			help_text = "The TA for this student, if any")
	# TODO unique together: user + semester
