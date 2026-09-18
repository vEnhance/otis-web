"""Student surveys, split so that anonymous feedback isn't directly linked.

A submission writes a SurveyCompletion, which records *that* a student responded,
and separately a GMFeedback and possibly an InstructorComment, which record *what*
they said.

Feedback rows keep ascending primary keys, since submission order helps when
reading them, so a submission must not write anything timestamped that would line
up with that order. In particular, the survey's achievement isn't granted on
submission but in bulk once the survey closes, via Survey.grant_achievements.
"""

import uuid

from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone

from core.models import Semester
from roster.models import Assistant, Student
from rpg.models import Achievement, AchievementUnlock


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

    @property
    def is_open(self) -> bool:
        return self.opens_at <= timezone.now() < self.closes_at

    def grant_achievements(self) -> int:
        """Unlocks the achievement for everyone who completed this survey.

        Only call this once the survey has closed: unlocks are timestamped in
        the order created, so granting while submissions trickle in would
        reveal submission order. Returns the number of new unlocks.
        """
        if self.achievement is None:
            return 0
        already = AchievementUnlock.objects.filter(achievement=self.achievement)
        # Completion pks are random, so this order says nothing about submissions.
        user_ids = (
            SurveyCompletion.objects.filter(survey=self)
            .exclude(student__user__in=already.values("user"))
            .order_by("pk")
            .values_list("student__user", flat=True)
        )
        unlocks = [
            AchievementUnlock(user_id=user_id, achievement=self.achievement)
            for user_id in user_ids
        ]
        AchievementUnlock.objects.bulk_create(unlocks, ignore_conflicts=True)
        return len(unlocks)


class SurveyCompletion(models.Model):
    """That a student submitted a survey, deliberately without a timestamp."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("survey", "student")

    def __str__(self) -> str:
        return f"{self.student} completed {self.survey}"


class GMFeedback(models.Model):
    """The GM-visible part of a submission: essay, satisfaction, anything else."""

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
    token = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="Secret in the private link to anonymous feedback and its reply, "
        "if the student asked for one",
    )
    is_read = models.BooleanField(default=False)
    reply = models.TextField(blank=True, help_text="Reply shown to the student")
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "GM feedback"

    def __str__(self) -> str:
        return f"GM feedback for {self.survey}"


class InstructorComment(models.Model):
    """Comments for the student's instructor."""

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
    is_read = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Comments for {self.assistant} in {self.survey}"
