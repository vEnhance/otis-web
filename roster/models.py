from __future__ import unicode_literals

import os
from datetime import timedelta
from hashlib import pbkdf2_hmac
from typing import Callable, List, TypedDict

from _pydecimal import Decimal
from core.models import Semester, Unit
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.timezone import localtime, now
from sql_util.aggregates import Exists, SubqueryAggregate

from .country_abbrevs import COUNTRY_CHOICES


class CurriculumRowTypeDict(TypedDict, total=False):
    unit: Unit
    number: int
    num_uploads: int
    semester_active: bool

    is_submitted: bool
    is_current: bool
    is_visible: bool
    is_accepted: bool
    is_rejected: bool

    sols_label: str


class Assistant(models.Model):
    """This is a wrapper object for a single assistant."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        help_text="The Django Auth user attached to the Assistant.",
    )
    shortname = models.CharField(
        max_length=18, help_text="Initials or short name for this Assistant"
    )
    unlisted_students = models.ManyToManyField(
        "Student",
        blank=True,
        related_name="unlisted_assistants",
        help_text="A list of students this assistant can see but which is not listed visibly.",
    )

    class Meta:
        ordering = ("shortname",)

    def __str__(self) -> str:
        return self.shortname

    @property
    def first_name(self) -> str:
        return self.user.first_name

    @property
    def last_name(self) -> str:
        return self.user.last_name

    @property
    def name(self) -> str:
        return self.user.get_full_name()

    def student_count(self) -> int:
        return self.student_set.count()  # type: ignore


class Student(models.Model):
    """This is really a pair of a user and a semester (with a display name),
    endowed with the data of the curriculum of that student.
    It also names the assistant of the student, if any."""

    pk: int
    invoice: "Invoice"
    unlisted_assistants: QuerySet["Assistant"]
    get_track_display: Callable[[], str]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="The Django auth user attached to the student",
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, help_text="The semester for this student"
    )
    assistant = models.ForeignKey(
        Assistant,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The assistant for this student, if any",
    )
    reg = models.OneToOneField(
        "StudentRegistration",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text="Link to the registration forms for the student",
    )

    curriculum = models.ManyToManyField(
        Unit,
        blank=True,
        related_name="students_taking",
        help_text="The choice of units that this student will work on",
    )
    unlocked_units = models.ManyToManyField(
        Unit,
        blank=True,
        related_name="students_unlocked",
        help_text="A list of units that the student is actively working on. "
        "Once the student submits a problem set, "
        "delete it from this list to mark them as complete.",
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
        help_text="The track that the student is enrolled in for this semester.",
    )

    legit = models.BooleanField(
        default=True,
        help_text="Whether this student is still active. "
        "Set to false for dummy accounts and the like. "
        "This will hide them from the master schedule, for example.",
    )
    newborn = models.BooleanField(
        default=True, help_text="Whether the student is newly created."
    )
    enabled = models.BooleanField(
        default=True, help_text="Allow student to submit/request units."
    )

    last_level_seen = models.PositiveSmallIntegerField(
        default=0, help_text="The last level the student was seen at."
    )

    class Meta:
        unique_together = (
            "user",
            "semester",
        )
        ordering = (
            "semester",
            "-legit",
            "track",
            "user__first_name",
            "user__last_name",
        )

    def __str__(self):
        return f"{self.name} ({self.pk})"

    def get_absolute_url(self):
        return reverse("portal", args=(self.pk,))

    def get_checksum(self, key: str) -> str:
        return pbkdf2_hmac(
            "sha256",
            (key + str(pow(3, self.pk, 961748927)) + "meow").encode("utf-8"),
            b"salt is yummy so is sugar",
            100000,
            dklen=18,
        ).hex()

    @property
    def first_name(self) -> str:
        if self.user is None:
            return "???"
        return self.user.first_name

    @property
    def last_name(self) -> str:
        if self.user is None:
            return "???"
        return self.user.last_name

    @property
    def short_name(self) -> str:
        if self.user is None:
            return "???"
        elif self.user.last_name != "":
            return self.user.first_name + " " + self.user.last_name[0]
        else:
            return self.name

    @property
    def name(self) -> str:
        if self.user:
            return self.user.get_full_name() or self.user.username
        else:
            return "?"

    @property
    def get_track(self) -> str:
        if self.assistant is None:
            return self.get_track_display()
        else:
            return self.get_track_display() + " + " + self.assistant.shortname

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
        queryset = (
            self.curriculum.all()
            .select_related("group")
            .annotate(
                num_uploads=SubqueryAggregate(
                    "uploadedfile", filter=Q(benefactor__pk=self.pk), aggregate=Count
                )
            )
        )
        if self.semester.uses_legacy_pset_system is True:
            return queryset.annotate(
                has_pset=Exists(
                    "uploadedfile",
                    filter=Q(benefactor__pk=self.pk, category="psets"),
                )
            )
        else:
            return queryset.annotate(
                has_pset=Exists("pset", filter=Q(student=self)),
                accepted=Exists("pset", filter=Q(student=self, status="A")),
                rejected=Exists("pset", filter=Q(student=self, status="R")),
            )

    def has_submitted_pset(self, unit: Unit) -> bool:
        if self.semester.uses_legacy_pset_system:
            return Unit.objects.filter(
                pk=unit.pk,
                uploadedfile__benefactor=self,
                uploadedfile__category="psets",
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

    def generate_curriculum_rows(self) -> List[CurriculumRowTypeDict]:
        curriculum = self.generate_curriculum_queryset().order_by("position")
        unlocked_units_pks = self.unlocked_units.values_list("pk", flat=True)

        rows = []
        for i, unit in enumerate(curriculum):
            n = i + 1
            row: CurriculumRowTypeDict = {}
            row["unit"] = unit
            row["number"] = n
            row["num_uploads"] = getattr(unit, "num_uploads", 0)

            row["semester_active"] = self.semester.active
            row["is_submitted"] = getattr(unit, "has_pset", False)
            row["is_current"] = unit.pk in unlocked_units_pks
            row["is_visible"] = row["is_submitted"] or row["is_current"]
            if self.semester.uses_legacy_pset_system is True:
                row["is_accepted"] = row["is_submitted"] and not row["is_current"]
                row["is_rejected"] = False
            else:
                row["is_accepted"] = getattr(unit, "accepted")
                row["is_rejected"] = getattr(unit, "rejected")
            rows.append(row)
        return rows

    @property
    def payment_status(self):
        """Returns one of several codes:
        -3: remind of upcoming payment for grace deadline
        -2: warn of late payment for grace deadline
        -1: lock late payment for grace deadline
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

        if self.invoice.forgive_date is not None:
            d = self.invoice.forgive_date - now
            if d < timedelta(days=-7):
                return -1
            elif d < timedelta(days=0):
                return -2
            elif d < timedelta(days=7):
                return -3
            else:
                return 4

        if self.semester.first_payment_deadline is not None and invoice.total_paid <= 0:
            d = self.semester.first_payment_deadline - now
            if d < timedelta(days=-7):
                return 3
            elif d < timedelta(days=0):
                return 2
            elif d < timedelta(days=7):
                return 1

        if (
            self.semester.most_payment_deadline is not None
            and invoice.total_paid < 2 * invoice.total_cost / 3
        ):
            d = self.semester.most_payment_deadline - now
            if d < timedelta(days=-7):
                return 7
            elif d < timedelta(days=0):
                return 6
            elif d < timedelta(days=7):
                return 5
        return 4

    @property
    def is_delinquent(self) -> bool:
        return self.payment_status % 4 == 3


class Invoice(models.Model):
    """Billing information object for students."""

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        help_text="The invoice that this student is for.",
    )
    preps_taught = models.SmallIntegerField(
        default=0,
        help_text="Number of semesters that development/preparation "
        "costs are charged.",
    )
    hours_taught = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Number of hours taught for.",
    )
    adjustment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Adjustment to the cost, e.g. for financial aid.",
    )
    credits = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Credit earned via internships",
    )
    extras = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Additional payment, e.g. for T-shirts.",
    )
    total_paid = models.DecimalField(
        max_digits=8, decimal_places=2, default=0, help_text="Amount paid."
    )
    updated_at = models.DateTimeField(auto_now=True)
    forgive_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When switched on, won't hard lock delinquents before this date.",
    )
    memo = models.TextField(blank=True, help_text="Internal note to self.")

    def __str__(self):
        return f"{self.pk or 0} ({self.total_paid}/{self.total_cost})"

    def get_absolute_url(self) -> str:
        return reverse("invoice", args=(self.pk,))

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
        return (
            self.prep_rate * self.preps_taught
            + self.hour_rate * self.hours_taught
            + self.extras
            + self.adjustment
        )

    @property
    def total_owed(self) -> Decimal:
        return self.total_cost - (self.total_paid + self.credits)

    @property
    def cleared(self) -> bool:
        """Whether or not the student owes anything"""
        return self.total_owed <= 0

    @property
    def track(self) -> str:
        return self.student.track


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
        max_length=15,
        choices=(
            ("INQ_ACT_UNLOCK", "Unlock now"),
            ("INQ_ACT_APPEND", "Add for later"),
            ("INQ_ACT_DROP", "Drop"),
            ("INQ_ACT_LOCK", "Lock (Drop + Add for later)"),
        ),
        help_text="Describe the action you want to make.",
    )
    status = models.CharField(
        max_length=10,
        choices=(
            ("INQ_ACC", "Accepted"),
            ("INQ_REJ", "Rejected"),
            ("INQ_NEW", "Pending"),
            ("INQ_HOLD", "On hold"),
        ),
        default="INQ_NEW",
        help_text="The current status of the petition.",
    )
    explanation = models.TextField(
        max_length=300, help_text="Short explanation for this request."
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Unit petition"
        verbose_name_plural = "Unit petitions"

    def __str__(self) -> str:
        return self.action_type + " " + str(self.unit)

    def run_accept(self):
        unit = self.unit
        if self.action_type == "INQ_ACT_UNLOCK":
            self.student.curriculum.add(unit)
            self.student.unlocked_units.add(unit)
        elif self.action_type == "INQ_ACT_APPEND":
            self.student.curriculum.add(unit)
        elif self.action_type == "INQ_ACT_DROP":
            self.student.curriculum.remove(unit)
            self.student.unlocked_units.remove(unit)
        elif self.action_type == "INQ_ACT_LOCK":
            self.student.unlocked_units.remove(unit)
        else:
            raise ValueError(f"No action {self.action_type}")
        self.status = "INQ_ACC"
        self.save()


def content_file_name(instance: "StudentRegistration", filename: str) -> str:
    return os.path.join(
        "agreement", str(instance.container.pk), instance.user.username + "_" + filename
    )


class RegistrationContainer(models.Model):
    semester = models.OneToOneField(
        Semester,
        help_text="Controls the settings for registering for a semester",
        on_delete=models.CASCADE,
    )
    passcode = models.CharField(
        max_length=128, help_text="The passcode for that year's registration"
    )
    allowed_tracks = models.CharField(
        max_length=256,
        help_text="A comma separated list of allowed tracks students can register for",
        blank=True,
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
        related_name="regs",
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
        default="C",
    )
    gender = models.CharField(
        max_length=2,
        default="",
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
        help_text="Enter your expected graduation year",
    )
    school_name = models.CharField(
        max_length=200, help_text="Enter the name of your high school"
    )
    aops_username = models.CharField(
        max_length=200,
        help_text="Enter your Art of Problem Solving username (leave blank for none)",
        blank=True,
    )

    agreement_form = models.FileField(
        null=True,
        # blank=False,
        help_text="Signed agreement form, as a single PDF",
        upload_to=content_file_name,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                ]
            )
        ],
    )
    processed = models.BooleanField(
        help_text="Whether Evan has dealt with this kid yet", default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    country = models.CharField(max_length=6, choices=COUNTRY_CHOICES, default="USA")

    class Meta:
        unique_together = (
            "user",
            "container",
        )

    def __str__(self) -> str:
        return self.user.username

    def get_absolute_url(self) -> str:
        try:
            student = Student.objects.get(
                user=self.user, semester=self.container.semester
            )
        except Student.DoesNotExist:
            return self.container.semester.get_absolute_url()
        else:
            return student.get_absolute_url()

    @property
    def name(self) -> str:
        return self.user.first_name + " " + self.user.last_name

    @property
    def grade(self) -> int:
        if self.graduation_year == 0:
            return 13
        else:
            return 12 - (self.graduation_year - self.container.semester.end_year)

    @property
    def about(self):
        return f"{self.grade}{self.gender or 'U'}"
