from __future__ import unicode_literals

from django.db import models
from django.contrib.auth import models as auth
import core

# Create your models here.

class TA(models.Model):
	"""This is a single user who is actually a TA.
	Currently don't need much information about them..."""
	user = models.ForeignKey(auth.User,
			help_text = "The Django Auth user attached to the TA")
	name = models.CharField(max_length = 80,
			help_text = "The display name for this TA (e.g. a nickname)")
	def __unicode__(self):
		return unicode(self.user)
	def student_count(self):
		return self.student_set.count()

class Student(models.Model):
	"""This is really a pair of a user and a semester,
	endowed with the data of the curriculum of that student.
	It also names the assistant of the student, if any."""
	user = models.ForeignKey(auth.User,
			help_text = "The Django Auth user attached to the student")
	name = models.CharField(max_length = 80,
			help_text = "The display name for this student (e.g. a nickname)")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this student")
	curriculum = models.ManyToManyField(core.models.Unit,
			help_text = "The choice of units that this student will work on")
	assistant = models.ForeignKey(TA, blank = True, null = True,
			help_text = "The TA for this student, if any")
	current_unit_index = models.SmallIntegerField(default = 0,
			help_text = "If this is equal to k, "
			"then the student has completed the first k units of his/her "
			"curriculum and is working on the (k+1)st unit")
	def __unicode__(self):
		return unicode(self.user)
	# TODO unique together: user + semester
