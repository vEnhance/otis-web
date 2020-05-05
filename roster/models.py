from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count, Q, Subquery, OuterRef, Exists

import core
import dashboard

class Assistant(models.Model):
	"""This is a wrapper object for a single assistant."""
	user = models.OneToOneField(User, on_delete = models.CASCADE,
			help_text = "The Django Auth user attached to the Assistant.")
	shortname = models.CharField(max_length = 10,
			help_text = "Initials or short name for this Assistant")
	unlisted_students = models.ManyToManyField("Student", blank = True,
			related_name = "unlisted_assistants",
			help_text = "A list of students this assistant can see "
					"but which is not listed visibly.")

	@property
	def first_name(self):
		return self.user.first_name
	@property
	def last_name(self):
		return self.user.last_name
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
			related_name = 'students_taking',
			help_text = "The choice of units that this student will work on")
	unlocked_units = models.ManyToManyField(core.models.Unit, blank = True,
			related_name = 'students_unlocked',
			help_text = "A list of units that the student may work on.")
	num_units_done = models.SmallIntegerField(default = 0,
			help_text = "The number of completed units. "
			"This is set manually for Evan's book-keeping.")
	vision = models.SmallIntegerField(default = 3,
			help_text = "Deprecated and no longer in use. To be deleted.")

	track = models.CharField(max_length = 5,
			choices = (
				("A", "Weekly"),
				("B", "Biweekly"),
				("BW", "Biwk. WS"),
				("C", "Corr."),
				("CW", "Corr. WS"),
				("E", "Ext."),
				("G", "Grad"),
				("N", "N.A."),
				("P", "Phantom"),
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
	def first_name(self):
		return self.user.first_name
	@property
	def last_name(self):
		return self.user.last_name
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
		return user.is_staff \
				or (self.assistant is not None and self.assistant.user == user) \
				or (self.unlisted_assistants.filter(user=user).exists())

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

	def has_submitted_pset(self, unit):
		return dashboard.models.UploadedFile.objects.filter(
				unit = unit,
				benefactor = self,
				category = 'psets')

	def check_unit_unlocked(self, unit):
		if self.newborn:
			return False
		elif self.unlocked_units.filter(pk=unit.id).exists():
			return True
		elif self.has_submitted_pset(unit):
			return True
		else:
			return False

	def generate_curriculum_rows(self, omniscient):
		curriculum = self.generate_curriculum_queryset()
		unlocked_units_ids = self.unlocked_units.values_list('id', flat=True)

		rows = []
		for i, unit in enumerate(curriculum):
			n = i+1
			row = {}
			row['unit'] = unit
			row['number'] = n
			row['num_uploads'] = unit.num_uploads or 0

			row['is_complete'] = unit.has_pset
			row['is_current'] = unit.id in unlocked_units_ids
			row['is_visible'] = row['is_complete'] or row['is_current']

			if row['is_complete']:
				row['sols_label'] = "Solutions"
			elif omniscient and row['is_visible']:
				row['sols_label'] = "Sol (hidden)"
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
				("UNLOCK", "Unlock now"),
				("APPEND", "Add for later"),
				("DROP",   "Drop"),
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
		if self.action_type == "UNLOCK":
			self.student.curriculum.add(unit)
			self.student.unlocked_units.add(unit)
		elif self.action_type == "APPEND":
			self.student.curriculum.add(unit)
		elif self.action_type == "DROP":
			self.student.curriculum.remove(unit)
			self.student.unlocked_units.remove(unit)
		self.status = "ACC"
		self.save()

	def __str__(self):
		return self.action_type + " " + str(self.unit)
	
	class Meta:
		ordering = ('-created_at',)
