from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count, Q, Subquery, OuterRef, Exists

import core
import dashboard

class Assistant(models.Model):
	"""This is a wrapper object for a single assistant.
	Just need a username at the moment..."""
	user = models.OneToOneField(User, on_delete = models.CASCADE,
			help_text = "The Django Auth user attached to the Assistant.")
	shortname = models.CharField(max_length = 10,
			help_text = "Initials or short name for this Assistant")
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
			on_delete = models.CASCADE,
			help_text = "The Django Auth user attached to the student")
	semester = models.ForeignKey(core.models.Semester,
			on_delete = models.CASCADE,
			help_text = "The semester for this student")
	assistant = models.ForeignKey(Assistant, blank = True, null = True,
			on_delete = models.SET_NULL,
			help_text = "The assistant for this student, if any")

	curriculum = models.ManyToManyField(core.models.Unit, blank = True,
			related_name = 'curriculum',
			help_text = "The choice of units that this student will work on")
	extra_units = models.ManyToManyField(core.models.Unit, blank = True,
			related_name = 'extra_units',
			help_text = "A list of units that the student "
			"can access out-of-order relative to their curriculum.")
	num_units_done = models.SmallIntegerField(default = 0,
			help_text = "If this is equal to k, "
			"then the student has completed the first k units of his/her "
			"curriculum and by default is working on the (k+1)st unit.")
	vision = models.SmallIntegerField(default = 3,
			help_text = "How many units ahead of the most "
			"recently completed unit the student can see.")

	track = models.CharField(max_length = 5,
			choices = (
				("A", "Weekly"),
				("B", "Biweekly"),
				("C", "Corr."),
				("E", "Ext."),
				("G", "Grad"),
				("N", "N.A."),
				),
			help_text = "The track that the student is enrolled in for this semester.")
	legit = models.BooleanField(default = True,
			help_text = "Whether this student is still active. "
			"Set to false for dummy accounts and the like. "
			"This will hide them from the master schedule, for example.")
	newborn = models.BooleanField(default = True,
			help_text = "Whether the student is newly created.")
	def __str__(self):
		return "%s (%s)" %(self.name, self.semester)

	@property
	def name(self):
		if self.user: return self.user.get_full_name() or self.user.username
		else: return "?"
	@property
	def get_track(self):
		if self.assistant is None:
			return self.get_track_display()
		else:
			return self.get_track_display() \
					+ " + " + self.assistant.shortname

	def is_taught_by(self, user):
		"""Checks whether the specified user
		is not the same as the student,
		but has permission to view and edit the student's files etc.
		(This means the user is either an assistant for that student
		or has staff privileges.)"""
		return user.is_staff or (self.assistant is not None \
				and self.assistant.user == user)
	def can_view_by(self, user):
		"""Checks whether the specified user
		is either same as the student,
		or is an instructor for that student."""
		return self.user == user or self.is_taught_by(user)
	class Meta:
		unique_together = ('user', 'semester',)
		ordering = ('semester', '-legit', 'track', 'user__first_name', 'user__last_name')
	
	@property
	def meets_evan(self):
		return (self.track == "A" or self.track == "B") and self.legit
	@property
	def calendar_url(self):
		if self.meets_evan:
			return self.semester.calendar_url_meets_evan
		else:
			return self.semester.calendar_url_no_meets_evan
	@property
	def curriculum_length(self):
		return self.curriculum.count()

	def generate_curriculum_queryset(self):
		return self.curriculum.all().annotate(
				num_uploads = Count('uploadedfile',
					filter = Q(uploadedfile__benefactor = self.id)),
				has_pset = Exists(
					dashboard.models.UploadedFile.objects.filter(
						unit=OuterRef('pk'),
						benefactor=self.id,
						category='psets')))\
				.order_by('-has_pset', 'position')

	def check_unit_unlocked(self, unit):
		if self.extra_units.filter(pk=unit.id).exists():
			return True
		curriculum = list(self.generate_curriculum_queryset())
		if not unit in curriculum:
			return False
		i = curriculum.index(unit)
		unit = curriculum[i] # grab the annotations
		if unit.has_pset:
			return True
		elif i <= self.num_units_done + (self.vision-1):
			return True
		else:
			return False

	def generate_curriculum_rows(self, omniscient):
		current_index = self.num_units_done
		curriculum = self.generate_curriculum_queryset()
		extra_units_ids = self.extra_units.values_list('id', flat=True)

		rows = []
		for n, unit in enumerate(curriculum):
			row = {}
			row['unit'] = unit
			row['number'] = n+1
			row['is_completed'] = unit.has_pset or n < current_index
			row['num_uploads'] = unit.num_uploads or 0
			row['is_current'] = (n == current_index)
			row['is_unlocked'] = row['is_completed'] \
					or row['is_current'] \
					or (unit.id in extra_units_ids) \
					or n <= current_index + (self.vision-1)

			if row['is_completed']:
				row['sols_label'] = "Solutions"
			elif omniscient and row['is_current']:
				row['sols_label'] = "Sols (current)"
			elif omniscient and row['is_unlocked']:
				row['sols_label'] = "Sols (future)"
			else:
				row['sols_label'] = None # solutions not shown
			rows.append(row)
		return rows

class Invoice(models.Model):
	"""Billing information object for students."""
	student = models.OneToOneField(Student,
			on_delete = models.CASCADE,
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
	def prep_rate(self):
		return self.student.semester.prep_rate
	@property
	def hour_rate(self):
		return self.student.semester.hour_rate

	@property
	def total_cost(self):
		return self.prep_rate*self.preps_taught + self.hour_rate*self.hours_taught
	@property
	def total_owed(self):
		return self.total_cost - self.total_paid
	@property
	def cleared(self):
		"""Whether or not the student owes anything"""
		return (self.total_owed <= 0)

	@property
	def track(self):
		return self.student.track

class UnitInquiry(models.Model):
	unit = models.ForeignKey(core.models.Unit,
			on_delete = models.CASCADE,
			help_text = "The unit being requested.")
	student = models.ForeignKey(Student,
			on_delete = models.CASCADE,
			help_text = "The student making the request")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	action_type = models.CharField(max_length = 10,
			choices = (
				("DROP", "Drop"),
				("ADD", "Add"),
				),
			help_text = "Describe the action you want to make.")
	status = models.CharField(max_length = 5,
			choices = (
				("ACC", "Approved"),
				("REJ", "Rejected"),
				("NEW", "Pending"),
				("HOLD", "On hold"),
				),
			default = "NEW",
			help_text = "The current status of the inquiry.")
	explanation = models.TextField(max_length = 300, blank=True,
			help_text="Short explanation for this request (if needed).")

	def run_accept(self):
		unit = self.unit
		if self.action_type == "DROP":
			self.student.curriculum.remove(unit)
			self.student.extra_units.remove(unit)
		elif self.action_type == "ADD":
			self.student.curriculum.add(unit)
			self.student.extra_units.add(unit)
		self.student.save()

		self.status = "ACC"
		self.save()

	def __str__(self):
		return self.action_type + " " + str(self.unit)
	
	class Meta:
		ordering = ('-created_at',)
