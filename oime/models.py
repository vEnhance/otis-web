from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class OIMEProposal(models.Model):
    SUBJECT_CHOICES = [
        ("A", "Algebra"),
        ("C", "Combinatorics"),
        ("G", "Geometry"),
        ("N", "Number Theory"),
    ]
    DIFFICULTY_CHOICES = [(i, str(i)) for i in range(1, 6)]

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="oime_proposals",
        help_text="The user who wrote this problem.",
    )
    statement = models.TextField(help_text="The problem statement, in LaTeX.")
    answer = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)],
        help_text="Integer answer (0-999).",
    )
    solution = models.TextField(help_text="Full solution write-up, in LaTeX.")
    subject = models.CharField(max_length=1, choices=SUBJECT_CHOICES)
    difficulty = models.IntegerField(
        choices=DIFFICULTY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        subject = self.get_subject_display()  # type: ignore[attr-defined]
        return f"{subject} D{self.difficulty} by {self.author.get_full_name() or self.author.username}"

    def get_absolute_url(self) -> str:
        return reverse("oime-proposal-detail", args=[self.pk])

    @property
    def time_limit_minutes(self) -> int:
        return 5 * self.difficulty + 5


class OIMESolverRole(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="oime_role",
    )
    is_serious = models.BooleanField(
        default=False,
        help_text="Serious solvers get timed attempts; casual solvers can browse freely.",
    )

    def __str__(self) -> str:
        role = "serious" if self.is_serious else "casual"
        return f"{self.user.username} ({role})"


class OIMEAttempt(models.Model):
    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("CORRECT", "Solved"),
        ("GAVE_UP", "Gave Up"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="oime_attempts",
    )
    proposal = models.ForeignKey(
        OIMEProposal,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="IN_PROGRESS")
    wrong_answers = models.IntegerField(default=0)
    solve_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Only set when status is CORRECT.",
    )

    class Meta:
        unique_together = [("user", "proposal")]

    def __str__(self) -> str:
        return f"{self.user.username} on {self.proposal}"

    @property
    def is_complete(self) -> bool:
        return self.status in ("CORRECT", "GAVE_UP")

    @property
    def time_expired(self) -> bool:
        if self.is_complete:
            return False
        elapsed = (timezone.now() - self.started_at).total_seconds()
        return elapsed > self.proposal.time_limit_minutes * 60

    @property
    def remaining_seconds(self) -> int:
        elapsed = (timezone.now() - self.started_at).total_seconds()
        return max(0, int(self.proposal.time_limit_minutes * 60 - elapsed))


class OIMEComment(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="oime_comments",
    )
    proposal = models.ForeignKey(
        OIMEProposal,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author.username} on {self.proposal}"
