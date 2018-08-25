from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User
import core


class Assistant(models.Model):
	"""This is a wrapper object for a single assistant.
	Just need a username at the moment..."""
	user = models.OneToOneField(User,
		help_text = "The Django Auth user attached to the Assistant.")
	@property
	def name(self):
		return self.user.get_full_name()
	def __str__(self):
		return self.name
	def student_count(self):
		return self.student_set.count()

class Student(models.Model):
	"""This is really a pair of a user and a semester (with a display name),
	endowed with the data of the curriculum of that student.
	It also names the assistant of the student, if any."""
	user = models.ForeignKey(User, blank = True, null = True,
			help_text = "The Django Auth user attached to the student")
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester for this student")
	curriculum = models.ManyToManyField(core.models.Unit, blank = True,
			help_text = "The choice of units that this student will work on")
	assistant = models.ForeignKey(Assistant, blank = True, null = True,
			help_text = "The assistant for this student, if any")
	current_unit_index = models.SmallIntegerField(default = 0,
			help_text = "If this is equal to k, "
			"then the student has completed the first k units of his/her "
			"curriculum and by default is working on the (k+1)st unit.")
	pointer_current_unit = models.ForeignKey(core.models.Unit,
			blank=True, null=True, related_name='pointer_unit',
			help_text = "If set, the counter will skip ahead "
			"so that the student is working on this unit instead.")
	track = models.CharField(max_length = 5,
			choices = (
				("A", "Weekly"),
				("B", "Biweekly"),
				("C", "Correspondence"),
				("N", "Not applicable"),
				),
			help_text = "")
	legit = models.BooleanField(default = True,
			help_text = "Whether this student is still active. "
			"Set to false for dummy accounts and the like. "
			"This will hide them from the master schedule, for example.")
	def __str__(self):
		return "%s (%s)" %(self.name, self.semester)
	@property
	def name(self):
		if self.user: return self.user.get_full_name() or self.user.username
		else: return "?"

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
		ordering = ('semester', '-legit', 'track',)
	
	@property
	def meets_evan(self):
		return (self.track == "A" or self.track == "B") and self.legit

	@property
	def curriculum_length(self):
		return self.curriculum.count()


# TODO rewrite this af I think
class Invoice(models.Model):
	"""Billing information object for students."""
	PREP_RATE = 320 # 320 per semester...
	HOUR_RATE = 80  # plus 80 per hour

	student = models.OneToOneField(Student,
			help_text = "The invoice that this student is for.")
	preps_taught = models.SmallIntegerField(default = 0,
			help_text = "Number of semesters that development/preparation "
			"costs are charged.")
	hours_taught = models.DecimalField(max_digits = 8,
			decimal_places = 2, default = 0,
			help_text = "Number of hours taught for.")
	total_paid = models.DecimalField(max_digits = 8,
			decimal_places = 2, default = 0,
			help_text = "Amount paid.")
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Invoice %d" %(self.id or 0,)

	@property
	def total_cost(self):
		return self.PREP_RATE*self.preps_taught + self.HOUR_RATE*self.hours_taught

	@property
	def total_owed(self):
		return self.total_cost - self.total_paid

	@property
	def cleared(self):
		"""Whether or not the student owes anything"""
		return (self.total_owed <= 0)
