from __future__ import unicode_literals

import datetime
import string

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.urls.base import reverse

from exams.calculator import expr_compute
from roster.models import Student


def expr_validator(value: str):
    try:
        x = float(expr_compute(value) or 0)
        assert abs(x) < 1e10000
    except OverflowError:
        raise ValidationError(r"This result has absolute value too large to parse.")
    except Exception:
        raise ValidationError("Could not evaluate this expression, please fix it")


def expr_validator_multiple(value: str):
    if value != "":
        for v in value.split(","):
            expr_validator(v)


class PracticeExam(models.Model):
    family = models.CharField(
        max_length=10,
        choices=(
            ("Waltz", "Waltz"),
            ("Foxtrot", "Foxtrot"),
        ),
        help_text="The family that the exam comes from.",
    )
    is_test = models.BooleanField(help_text="Whether this is a quiz or test")
    number = models.PositiveSmallIntegerField(
        help_text="The number of the assignment (e.g. Test 8, Quiz D) "
    )

    # For quizzes only
    answer1 = models.CharField(
        max_length=128, validators=[expr_validator_multiple], blank=True
    )
    answer2 = models.CharField(
        max_length=128, validators=[expr_validator_multiple], blank=True
    )
    answer3 = models.CharField(
        max_length=128, validators=[expr_validator_multiple], blank=True
    )
    answer4 = models.CharField(
        max_length=128, validators=[expr_validator_multiple], blank=True
    )
    answer5 = models.CharField(
        max_length=128, validators=[expr_validator_multiple], blank=True
    )
    url1 = models.URLField(max_length=128, blank=True, validators=[URLValidator()])
    url2 = models.URLField(max_length=128, blank=True, validators=[URLValidator()])
    url3 = models.URLField(max_length=128, blank=True, validators=[URLValidator()])
    url4 = models.URLField(max_length=128, blank=True, validators=[URLValidator()])
    url5 = models.URLField(max_length=128, blank=True, validators=[URLValidator()])

    start_date = models.DateField(
        null=True, blank=True, help_text="When the assignment opens."
    )
    due_date = models.DateField(
        null=True, blank=True, help_text="When the assignment should be due."
    )

    class Meta:
        ordering = ("family", "-is_test", "number")
        unique_together = ("family", "is_test", "number")

    def __str__(self) -> str:
        if self.is_test:
            return self.family + " Test " + self.get_number_display()
        else:
            return self.family + " Quiz " + self.get_number_display()

    def get_absolute_url(self) -> str:
        return reverse("exam-pdf", args=(self.pk,))

    @property
    def pdfname(self) -> str:
        kind = "Exam" if self.is_test else "Quiz"
        return f"{kind}-{self.family}-{self.get_number_display()}.pdf"

    def get_number_display(self) -> str:
        if self.is_test:
            return f"{self.number:02d}"
        else:
            return string.ascii_uppercase[self.number - 1]

    @property
    def overdue(self) -> bool:
        return (self.due_date is not None) and (self.due_date < datetime.date.today())

    @property
    def deadline(self) -> datetime.datetime | None:
        if self.is_test is True or self.was_extended:
            return self.due_date
        else:
            return self.due_date + datetime.timedelta(days=-7)

    @property
    def was_extended(self) -> bool:
        return (
            self.due_date is not None
            and self.is_test is False
            and datetime.date.today() >= self.due_date + datetime.timedelta(days=-9)
        )

    @property
    def started(self) -> bool:
        if self.start_date is None:
            return True
        return self.start_date <= datetime.date.today()

    @property
    def current(self) -> bool:
        return self.started and not self.overdue


class ExamAttempt(models.Model):
    quiz = models.ForeignKey(
        PracticeExam, on_delete=models.CASCADE, help_text="The quiz being submitted for"
    )
    score = models.SmallIntegerField(
        null=True, blank=True, help_text="The number of correct answers"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, help_text="The student taking the exam"
    )
    guess1 = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Problem 1 response",
        validators=[
            expr_validator,
        ],
    )
    guess2 = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Problem 2 response",
        validators=[
            expr_validator,
        ],
    )
    guess3 = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Problem 3 response",
        validators=[
            expr_validator,
        ],
    )
    guess4 = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Problem 4 response",
        validators=[
            expr_validator,
        ],
    )
    guess5 = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Problem 5 response",
        validators=[
            expr_validator,
        ],
    )
    submit_time = models.DateTimeField(
        help_text="When the quiz was submitted", auto_now_add=True
    )
    student_pk: int
    quiz_pk: int

    class Meta:
        unique_together = (
            "quiz",
            "student",
        )

    def __str__(self) -> str:
        return f"{self.student} tries {self.quiz}"

    def get_absolute_url(self) -> str:
        return reverse("quiz", args=(self.student_pk, self.quiz_pk))


class MockCompleted(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(PracticeExam, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            "student",
            "exam",
        )
        verbose_name_plural = "Mock completions"
