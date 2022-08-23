from __future__ import unicode_literals

import os
from datetime import timedelta
from hashlib import pbkdf2_hmac
from typing import Any, Callable, Dict, List

from _pydecimal import Decimal
from core.models import Semester, Unit
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.urls import reverse_lazy
from django.utils.timezone import localtime
from sql_util.aggregates import Exists, SubqueryAggregate


class Assistant(models.Model):
	"""This is a wrapper object for a single assistant."""
	user = models.OneToOneField(
		User, on_delete=models.CASCADE, help_text="The Django Auth user attached to the Assistant."
	)
	shortname = models.CharField(
		max_length=18, help_text="Initials or short name for this Assistant"
	)
	unlisted_students = models.ManyToManyField(
		"Student",
		blank=True,
		related_name="unlisted_assistants",
		help_text="A list of students this assistant can see but which is not listed visibly."
	)

	@property
	def first_name(self) -> str:
		return self.user.first_name

	@property
	def last_name(self) -> str:
		return self.user.last_name

	@property
	def name(self) -> str:
		return self.user.get_full_name()

	def __str__(self) -> str:
		return self.shortname

	def student_count(self) -> int:
		return self.student_set.count()  # type: ignore

	class Meta:
		ordering = ('shortname', )


class Student(models.Model):
	"""This is really a pair of a user and a semester (with a display name),
	endowed with the data of the curriculum of that student.
	It also names the assistant of the student, if any."""
	user = models.ForeignKey(
		User, on_delete=models.CASCADE, help_text="The Django auth user attached to the student"
	)
	semester = models.ForeignKey(
		Semester, on_delete=models.CASCADE, help_text="The semester for this student"
	)
	assistant = models.ForeignKey(
		Assistant,
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
		help_text="The assistant for this student, if any"
	)

	curriculum = models.ManyToManyField(
		Unit,
		blank=True,
		related_name='students_taking',
		help_text="The choice of units that this student will work on"
	)
	unlocked_units = models.ManyToManyField(
		Unit,
		blank=True,
		related_name='students_unlocked',
		help_text="A list of units that the student is actively working on. "
		"Once the student submits a problem set, "
		"delete it from this list to mark them as complete."
	)

	track = models.CharField(
		max_length=5,
		choices=(
			("A", "Weekly"),
			("B", "Biweekly"),
			("C", "Corr."),
			("E", "Ext."),
			("G", "Grad"),
			("N", "N.A."),
			("P", "Phantom"),
		),
		help_text="The track that the student is enrolled in for this semester."
	)

	legit = models.BooleanField(
		default=True,
		help_text="Whether this student is still active. "
		"Set to false for dummy accounts and the like. "
		"This will hide them from the master schedule, for example."
	)
	newborn = models.BooleanField(default=True, help_text="Whether the student is newly created.")
	enabled = models.BooleanField(
		default=True, help_text="Allow student to submit/request units."
	)
	public = models.BooleanField(
		default=False, 
		help_text="Whether student name appears on public leaderboards, "
		"like the diamonds leaderboard."
	)

	last_level_seen = models.PositiveSmallIntegerField(
		default=0, help_text="The last level the student was seen at."
	)

	id: int
	invoice: 'Invoice'
	unlisted_assistants: QuerySet['Assistant']

	def get_checksum(self, key: str) -> str:
		return pbkdf2_hmac(
			'sha256', (key + str(pow(3, self.id, 961748927)) + 'meow').encode('utf-8'),
			b'salt is yummy so is sugar',
			100000,
			dklen=18
		).hex()

	def __str__(self):
		return f"{self.name} ({self.semester})"

	def get_absolute_url(self):
		return reverse_lazy('portal', args=(self.id, ))

	@property
	def first_name(self) -> str:
		if self.user is None:
			return '???'
		return self.user.first_name

	@property
	def last_name(self) -> str:
		if self.user is None:
			return '???'
		return self.user.last_name

	@property
	def name(self) -> str:
		if self.user:
			return self.user.get_full_name() or self.user.username
		else:
			return "?"

	get_track_display: Callable[[], str]

	@property
	def get_track(self) -> str:
		if self.assistant is None:
			return self.get_track_display()
		else:
			return self.get_track_display() + " + " + self.assistant.shortname

	class Meta:
		unique_together = (
			'user',
			'semester',
		)
		ordering = ('semester', '-legit', 'track', 'user__first_name', 'user__last_name')

	@property
	def meets_evan(self) -> bool:
		return (self.track == "A" or self.track == "B") and self.legit

	@property
	def calendar_url(self) -> str:
		if self.meets_evan:
			return self.semester.calendar_url_meets_evan
		else:
			return self.semester.calendar_url_no_meets_evan

	@property
	def curriculum_length(self) -> int:
		return self.curriculum.count()

	def generate_curriculum_queryset(self) -> QuerySet[Unit]:
		queryset = self.curriculum.all().select_related('group').annotate(
			num_uploads=SubqueryAggregate(
				'uploadedfile', filter=Q(benefactor__pk=self.id), aggregate=Count
			)
		)
		if self.semester.uses_legacy_pset_system is True:
			return queryset.annotate(
				has_pset=Exists(
					'uploadedfile',
					filter=Q(benefactor__pk=self.id, category='psets'),
				)
			)
		else:
			return queryset.annotate(
				has_pset=Exists('pset', filter=Q(student=self)),
				approved=Exists('pset', filter=Q(student=self, approved=True))
			)

	def has_submitted_pset(self, unit: Unit) -> bool:
		if self.semester.uses_legacy_pset_system:
			return Unit.objects.filter(
				pk=unit.pk, uploadedfile__benefactor=self, uploadedfile__category='psets'
			).exists()
		else:
			return Unit.objects.filter(pk=unit.pk, pset__student=self).exists()

	def check_unit_unlocked(self, unit: Unit) -> bool:
		if self.newborn:
			return False
		elif self.unlocked_units.filter(pk=unit.pk).exists():
			return True
		elif self.has_submitted_pset(unit):
			return True
		else:
			return False

	def generate_curriculum_rows(self, omniscient: bool) -> List[Dict[str, Any]]:
		curriculum = self.generate_curriculum_queryset().order_by('position')
		unlocked_units_ids = self.unlocked_units.values_list('id', flat=True)

		rows = []
		for i, unit in enumerate(curriculum):
			n = i + 1
			row: Dict[str, Any] = {}
			row['unit'] = unit
			row['number'] = n
			row['num_uploads'] = getattr(unit, 'num_uploads', 0)

			row['is_submitted'] = getattr(unit, 'has_pset', False)
			row['is_current'] = unit.pk in unlocked_units_ids
			row['is_visible'] = row['is_submitted'] or row['is_current']
			if self.semester.uses_legacy_pset_system is True:
				row['is_approved'] = row['is_submitted'] and not row['is_current']
			else:
				row['is_approved'] = getattr(unit, 'approved')

			if row['is_submitted'] or (row['is_visible'] and self.semester.active is False):
				row['sols_label'] = "🗝️"
			elif omniscient and row['is_visible']:
				row['sols_label'] = "㊙️"
			else:
				row['sols_label'] = None  # solutions not shown
			rows.append(row)
		return rows

	@property
	def payment_status(self):
		"""Returns one of several codes:
			0: student is clear (no invoice exists or total owed is nonpositive)
			1: remind of upcoming payment for initial deadline
			2: warn of late payment for initial deadline
			3: lock late payment for initial deadline
			4: no warning yet, but student has something owed
			5: remind of upcoming payment for primary deadline
			6: warn of late payment for primary deadline
			7: lock late payment for primary deadline
			"""
		if self.semester.show_invoices is False:
			return 0
		try:
			invoice = self.invoice
		except ObjectDoesNotExist:
			return 0

		assert invoice is not None
		if invoice.total_owed <= 0:
			return 0

		now = localtime()

		if self.semester.first_payment_deadline is not None and invoice.total_paid <= 0:
			d = self.semester.first_payment_deadline - now
			if d < timedelta(days=-7):
				return 3
			elif d < timedelta(days=0):
				return 2
			elif d < timedelta(days=7):
				return 1

		if self.semester.most_payment_deadline is not None and invoice.total_paid < 2 * invoice.total_cost / 3:
			d = self.semester.most_payment_deadline - now
			if d < timedelta(days=-7):
				return 7
			elif d < timedelta(days=0):
				return 6
			elif d < timedelta(days=7):
				return 5
		return 4

	@property
	def is_payment_locked(self):
		return self.payment_status % 4 == 3

	@property
	def is_delinquent(self):
		return self.is_payment_locked and self.invoice.forgive is False


class Invoice(models.Model):
	"""Billing information object for students."""
	student = models.OneToOneField(
		Student, on_delete=models.CASCADE, help_text="The invoice that this student is for."
	)
	preps_taught = models.SmallIntegerField(
		default=0,
		help_text="Number of semesters that development/preparation "
		"costs are charged."
	)
	hours_taught = models.DecimalField(
		max_digits=8, decimal_places=2, default=0, help_text="Number of hours taught for."
	)
	adjustment = models.DecimalField(
		max_digits=8,
		decimal_places=2,
		default=0,
		help_text="Adjustment to the cost, e.g. for financial aid."
	)
	extras = models.DecimalField(
		max_digits=8,
		decimal_places=2,
		default=0,
		help_text="Additional payment, e.g. for T-shirts."
	)
	total_paid = models.DecimalField(
		max_digits=8, decimal_places=2, default=0, help_text="Amount paid."
	)
	updated_at = models.DateTimeField(auto_now=True)
	forgive = models.BooleanField(
		default=False, help_text="When switched on, won't hard-lock delinquents."
	)
	memo = models.TextField(blank=True, help_text="Internal note to self.")

	def __str__(self):
		return f"Invoice {self.pk or 0}"

	@property
	def prep_rate(self) -> int:
		return self.student.semester.prep_rate

	@property
	def prep_total(self) -> int:
		return self.prep_rate * self.preps_taught

	@property
	def hour_rate(self) -> int:
		return self.student.semester.hour_rate

	@property
	def hours_total(self) -> Decimal:
		return self.hour_rate * self.hours_taught

	@property
	def total_cost(self) -> Decimal:
		return self.prep_rate * self.preps_taught + self.hour_rate * self.hours_taught + self.extras + self.adjustment

	@property
	def total_owed(self) -> Decimal:
		return self.total_cost - self.total_paid

	@property
	def cleared(self) -> bool:
		"""Whether or not the student owes anything"""
		return (self.total_owed <= 0)

	@property
	def track(self) -> str:
		return self.student.track

	def get_absolute_url(self) -> str:
		return reverse_lazy('invoice', args=(self.pk, ))


class UnitInquiry(models.Model):
	unit = models.ForeignKey(
		Unit, on_delete=models.CASCADE, help_text="The unit being requested."
	)
	student = models.ForeignKey(
		Student, on_delete=models.CASCADE, help_text="The student making the request"
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	action_type = models.CharField(
		max_length=10,
		choices=(
			("UNLOCK", "Unlock now"),
			("APPEND", "Add for later"),
			("DROP", "Drop"),
		),
		help_text="Describe the action you want to make."
	)
	status = models.CharField(
		max_length=5,
		choices=(
			("ACC", "Approved"),
			("REJ", "Rejected"),
			("NEW", "Pending"),
			("HOLD", "On hold"),
		),
		default="NEW",
		help_text="The current status of the petition."
	)
	explanation = models.TextField(
		max_length=300, blank=True, help_text="Short explanation for this request (if needed)."
	)

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
		else:
			raise ValueError(f"No action {self.action_type}")
		self.status = "ACC"
		self.save()

	def __str__(self) -> str:
		return self.action_type + " " + str(self.unit)

	class Meta:
		ordering = ('-created_at', )
		verbose_name = "Unit petition"
		verbose_name_plural = "Unit petitions"


def content_file_name(instance: 'StudentRegistration', filename: str) -> str:
	return os.path.join(
		"agreement", str(instance.container.id), instance.user.username + '_' + filename
	)


class RegistrationContainer(models.Model):
	semester = models.OneToOneField(
		Semester,
		help_text="Controls the settings for registering for a semester",
		on_delete=models.CASCADE,
	)
	end_year = models.IntegerField(help_text="The year in which OTIS will end")
	passcode = models.CharField(
		max_length=128, help_text="The passcode for that year's registration"
	)
	num_preps = models.PositiveSmallIntegerField(
		default=2, help_text="Number of preps to bill for"
	)
	allowed_tracks = models.CharField(
		max_length=256,
		help_text="A comma separated list of allowed tracks students can register for",
		blank=True
	)

	def __str__(self):
		return str(self.semester)


class StudentRegistration(models.Model):
	GENDER_CHOICES = (
		("M", "Male"),
		("F", "Female"),
		("H", "Nonbinary"),
		("O", "Other"),
		("U", "Prefer not to say"),
	)
	user = models.ForeignKey(
		User,
		help_text="The user to attach",
		on_delete=models.CASCADE,
		related_name='regs',
	)
	container = models.ForeignKey(
		RegistrationContainer,
		help_text="Where to register for",
		on_delete=models.CASCADE,
	)
	parent_email = models.EmailField(
		help_text="An email address "
		"in case Evan needs to contact your parents or something."
	)
	track = models.CharField(
		verbose_name="Proposed Track",
		max_length=6,
		choices=(
			("C", "Correspondence"),
			("B", "Meeting with Evan"),
			("E", "Meeting with another instructor"),
			("N", "None of the above"),
		),
		default="C"
	)
	gender = models.CharField(
		max_length=2,
		default='',
		choices=GENDER_CHOICES,
		help_text="If you are comfortable answering, "
		"specify which gender you most closely identify with.",
	)

	graduation_year = models.IntegerField(
		choices=(
			(0, "Already graduated high school"),
			(2021, "Graduating in 2021"),
			(2022, "Graduating in 2022"),
			(2023, "Graduating in 2023"),
			(2024, "Graduating in 2024"),
			(2025, "Graduating in 2025"),
			(2026, "Graduating in 2026"),
			(2027, "Graduating in 2027"),
			(2028, "Graduating in 2028"),
			(2029, "Graduating in 2029"),
		),
		help_text="Enter your expected graduation year"
	)
	school_name = models.CharField(max_length=200, help_text="Enter the name of your high school")
	aops_username = models.CharField(
		max_length=200,
		help_text="Enter your Art of Problem Solving username (leave blank for none)",
		blank=True
	)

	agreement_form = models.FileField(
		null=True,
		blank=False,
		help_text="Signed agreement form, as a single PDF",
		upload_to=content_file_name,
		validators=[FileExtensionValidator(allowed_extensions=[
			'pdf',
		])]
	)
	processed = models.BooleanField(
		help_text="Whether Evan has dealt with this kid yet", default=False
	)
	country = models.CharField(
		max_length=6,
		choices=(
			("AFG", "Afghanistan (AFG)"),
			("ALB", "Albania (ALB)"),
			("ALG", "Algeria (ALG)"),
			("AGO", "Angola (AGO)"),
			("ARG", "Argentina (ARG)"),
			("ARM", "Armenia (ARM)"),
			("AUS", "Australia (AUS)"),
			("AUT", "Austria (AUT)"),
			("AZE", "Azerbaijan (AZE)"),
			("BAH", "Bahrain (BAH)"),
			("BGD", "Bangladesh (BGD)"),
			("BLR", "Belarus (BLR)"),
			("BEL", "Belgium (BEL)"),
			("BEN", "Benin (BEN)"),
			("BOL", "Bolivia (BOL)"),
			("BIH", "Bosnia and Herzegovina (BIH)"),
			("BWA", "Botswana (BWA)"),
			("BRA", "Brazil (BRA)"),
			("BRU", "Brunei (BRU)"),
			("BGR", "Bulgaria (BGR)"),
			("BFA", "Burkina Faso (BFA)"),
			("KHM", "Cambodia (KHM)"),
			("CAN", "Canada (CAN)"),
			("CHI", "Chile (CHI)"),
			("CHN", "People's Republic of China (CHN)"),
			("COL", "Colombia (COL)"),
			("CIS", "Commonwealth of Independent States (CIS)"),
			("CRI", "Costa Rica (CRI)"),
			("HRV", "Croatia (HRV)"),
			("CUB", "Cuba (CUB)"),
			("CYP", "Cyprus (CYP)"),
			("CZE", "Czech Republic (CZE)"),
			("CZS", "Czechoslovakia (CZS)"),
			("DEN", "Denmark (DEN)"),
			("DOM", "Dominican Republic (DOM)"),
			("ECU", "Ecuador (ECU)"),
			("EGY", "Egypt (EGY)"),
			("EST", "Estonia (EST)"),
			("FIN", "Finland (FIN)"),
			("FRA", "France (FRA)"),
			("GMB", "Gambia (GMB)"),
			("GEO", "Georgia (GEO)"),
			("GDR", "German Democratic Republic (GDR)"),
			("GER", "Germany (GER)"),
			("GHA", "Ghana (GHA)"),
			("HEL", "Greece (HEL)"),
			("GTM", "Guatemala (GTM)"),
			("HND", "Honduras (HND)"),
			("HKG", "Hong Kong (HKG)"),
			("HUN", "Hungary (HUN)"),
			("ISL", "Iceland (ISL)"),
			("IND", "India (IND)"),
			("IDN", "Indonesia (IDN)"),
			("IRQ", "Iraq (IRQ)"),
			("IRN", "Islamic Republic of Iran (IRN)"),
			("IRL", "Ireland (IRL)"),
			("ISR", "Israel (ISR)"),
			("ITA", "Italy (ITA)"),
			("CIV", "Ivory Coast (CIV)"),
			("JAM", "Jamaica (JAM)"),
			("JPN", "Japan (JPN)"),
			("KAZ", "Kazakhstan (KAZ)"),
			("KEN", "Kenya (KEN)"),
			("PRK", "Democratic People's Republic of Korea (PRK)"),
			("KOR", "Republic of Korea (KOR)"),
			("KSV", "Kosovo (KSV)"),
			("KWT", "Kuwait (KWT)"),
			("KGZ", "Kyrgyzstan (KGZ)"),
			("LAO", "Laos (LAO)"),
			("LVA", "Latvia (LVA)"),
			("LIE", "Liechtenstein (LIE)"),
			("LTU", "Lithuania (LTU)"),
			("LUX", "Luxembourg (LUX)"),
			("MAC", "Macau (MAC)"),
			("MDG", "Madagascar (MDG)"),
			("MAS", "Malaysia (MAS)"),
			("MRT", "Mauritania (MRT)"),
			("MEX", "Mexico (MEX)"),
			("MDA", "Republic of Moldova (MDA)"),
			("MNG", "Mongolia (MNG)"),
			("MNE", "Montenegro (MNE)"),
			("MAR", "Morocco (MAR)"),
			("MOZ", "Mozambique (MOZ)"),
			("MMR", "Myanmar (MMR)"),
			("NPL", "Nepal (NPL)"),
			("NLD", "Netherlands (NLD)"),
			("NZL", "New Zealand (NZL)"),
			("NIC", "Nicaragua (NIC)"),
			("NGA", "Nigeria (NGA)"),
			("MKD", "North Macedonia (MKD)"),
			("NOR", "Norway (NOR)"),
			("OMN", "Oman (OMN)"),
			("PAK", "Pakistan (PAK)"),
			("PAN", "Panama (PAN)"),
			("PAR", "Paraguay (PAR)"),
			("PER", "Peru (PER)"),
			("PHI", "Philippines (PHI)"),
			("POL", "Poland (POL)"),
			("POR", "Portugal (POR)"),
			("PRI", "Puerto Rico (PRI)"),
			("ROU", "Romania (ROU)"),
			("RUS", "Russian Federation (RUS)"),
			("RWA", "Rwanda (RWA)"),
			("SLV", "El Salvador (SLV)"),
			("SAU", "Saudi Arabia (SAU)"),
			("SEN", "Senegal (SEN)"),
			("SRB", "Serbia (SRB)"),
			("SCG", "Serbia and Montenegro (SCG)"),
			("SGP", "Singapore (SGP)"),
			("SVK", "Slovakia (SVK)"),
			("SVN", "Slovenia (SVN)"),
			("SAF", "South Africa (SAF)"),
			("ESP", "Spain (ESP)"),
			("LKA", "Sri Lanka (LKA)"),
			("SWE", "Sweden (SWE)"),
			("SUI", "Switzerland (SUI)"),
			("SYR", "Syria (SYR)"),
			("TWN", "Taiwan (TWN)"),
			("TJK", "Tajikistan (TJK)"),
			("TZA", "Tanzania (TZA)"),
			("THA", "Thailand (THA)"),
			("TTO", "Trinidad and Tobago (TTO)"),
			("TUN", "Tunisia (TUN)"),
			("TUR", "Turkey (TUR)"),
			("NCY", "Turkish Republic of Northern Cyprus (NCY)"),
			("TKM", "Turkmenistan (TKM)"),
			("UGA", "Uganda (UGA)"),
			("UKR", "Ukraine (UKR)"),
			("UAE", "United Arab Emirates (UAE)"),
			("UNK", "United Kingdom (UNK)"),
			("USA", "United States of America (USA)"),
			("URY", "Uruguay (URY)"),
			("USS", "Union of Soviet Socialist Republics (USS)"),
			("UZB", "Uzbekistan (UZB)"),
			("VEN", "Venezuela (VEN)"),
			("VNM", "Vietnam (VNM)"),
			("YEM", "Yemen (YEM)"),
			("YUG", "Yugoslavia (YUG)"),
			("ZWE", "Zimbabwe (ZWE)"),
		),
		default="USA"
	)

	@property
	def name(self) -> str:
		return self.user.first_name + ' ' + self.user.last_name

	@property
	def about(self):
		if self.graduation_year == 0:
			grade = 13
		else:
			grade = 12 - (self.graduation_year - self.container.end_year)
		return f"{grade}{self.gender or 'U'}"

	class Meta:
		unique_together = (
			'user',
			'container',
		)

	def __str__(self) -> str:
		return self.user.username

	def get_absolute_url(self) -> str:
		try:
			student = Student.objects.get(user=self.user, semester=self.container.semester)
		except Student.DoesNotExist:
			print(self.container.semester.get_absolute_url())
			return self.container.semester.get_absolute_url()
		else:
			print(student.get_absolute_url())
			return student.get_absolute_url()
