"""Student surveys, split so that anonymous feedback can't be traced back.

A submission writes a SurveyCompletion, which records *that* a student responded,
and separately a GMFeedback and possibly an InstructorComment, which record *what*
they said. Nothing links the completion to the feedback: the feedback rows have
random primary keys and no timestamps, so neither insertion order nor the time of
the diamond unlock can match an anonymous row to its author.
"""

import uuid

from django.core.validators import MaxValueValidator
from django.db import models

from core.models import Semester
from roster.models import Assistant, Student
from rpg.models import Achievement


class Survey(models.Model):
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        help_text="The semester whose students take this survey",
    )
    name = models.CharField(max_length=80, help_text="For example, Survey 1")
    opens_at = models.DateTimeField(help_text="When submissions open")
    closes_at = models.DateTimeField(help_text="When submissions close")
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Achievement granted for submitting, if the student lacks it",
    )
    essay_prompt = models.TextField(help_text="Prompt for the required GM essay")
    instructor_comments_prompt = models.TextField(
        blank=True,
        help_text="Prompt for comments to the instructor; leave blank to not ask",
    )
    satisfaction_prompt = models.TextField(
        blank=True,
        help_text="Prompt for the satisfaction scale; leave blank to not ask",
    )
    anything_else_prompt = models.TextField(
        blank=True,
        help_text="Prompt for anything else for the GM; leave blank to not ask",
    )

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(opens_at__lt=models.F("closes_at")),
                name="%(app_label)s_%(class)s_opens_before_closes",
            ),
        )

    def __str__(self) -> str:
        return f"{self.semester}: {self.name}"


class SurveyCompletion(models.Model):
    """That a student submitted a survey, deliberately without a timestamp."""

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("survey", "student")

    def __str__(self) -> str:
        return f"{self.student} completed {self.survey}"


class GMFeedback(models.Model):
    """The GM-visible part of a submission: essay, satisfaction, anything else."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The student who signed this feedback, or empty if anonymous",
    )
    essay = models.TextField()
    satisfaction = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(7)],
        help_text="Satisfaction from 0 to 7, if the survey asked",
    )
    anything_else = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    reply = models.TextField(
        blank=True, help_text="Reply shown to the student, if signed"
    )
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "GM feedback"

    def __str__(self) -> str:
        return f"GM feedback for {self.survey}"


class InstructorComment(models.Model):
    """Comments for the student's instructor, which the GM screens before forwarding."""

    STATUS_CHOICES = (
        ("UNREAD", "Unread"),
        ("FORWARDED", "Forwarded"),
        ("WITHHELD", "Withheld"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The student who signed these comments, or empty if anonymous",
    )
    assistant = models.ForeignKey(
        Assistant,
        on_delete=models.CASCADE,
        help_text="The student's assistant at the time of submission",
    )
    comments = models.TextField()
    status = models.CharField(
        max_length=9,
        choices=STATUS_CHOICES,
        default="UNREAD",
    )

    def __str__(self) -> str:
        return f"Comments for {self.assistant} in {self.survey}"
