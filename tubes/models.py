from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Tube(models.Model):
    """This is a container in which testsolving happens.
    Since calling it anything related to tests will be super confusing with unit tests,
    we just call them tubes instead. Test tubes, or something."""

    STATUS_CHOICES = (
        ("TB_ACTIVE", "Active"),
        ("TB_HIDDEN", "Hidden"),
        ("TB_DONE", "Completed"),
    )

    display_name = models.CharField(max_length=128)
    description = models.TextField(
        help_text="A short description what this is about.", blank=True
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    main_url = models.URLField(help_text="Main URL for viewing the proposals.")
    accepting_signups = models.BooleanField(
        help_text="Whether to allow people to join", default=True
    )

    def __str__(self) -> str:
        return self.display_name

    def get_absolute_url(self) -> str:
        return self.main_url


class JoinRecord(models.Model):
    user = models.ForeignKey(
        User,
        help_text="The user who joined.",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    tube = models.ForeignKey(
        Tube, help_text="The tube the user joined.", on_delete=models.CASCADE
    )
    activation_time = models.DateTimeField(null=True, blank=True)
    invite_url = models.URLField(help_text="The URL for joining", blank=True)

    def __str__(self) -> str:
        return self.invite_url if self.invite_url else f"Join #{self.pk}"


# ---------------------------------------------------------------------------
# OIME models
# ---------------------------------------------------------------------------


class OIMEContributor(models.Model):
    """A student who participates in OIME (as proposer and/or testsolver)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="oime_contributor",
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Name used in credits when problems are attributed.",
    )
    spoil_before = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, this contributor is spoiled on all proposals created before this time "
        "and cannot start new timed attempts on them.",
    )

    def __str__(self) -> str:
        return self.display_name


class OIMEProposal(models.Model):
    SUBJECT_CHOICES = [
        ("A", "Algebra"),
        ("C", "Combinatorics"),
        ("G", "Geometry"),
        ("N", "Number Theory"),
    ]
    DIFFICULTY_CHOICES = [
        (1, "Tier I (AIME 1-3): 10 minutes"),
        (2, "Tier II (AIME 4-6): 15 minutes"),
        (3, "Tier III (AIME 7-9): 20 minutes"),
        (4, "Tier IV (AIME 10-12): 25 minutes"),
        (5, "Tier V (AIME 13-15): 30 minutes"),
    ]

    author = models.ForeignKey(
        OIMEContributor,
        on_delete=models.CASCADE,
        related_name="proposals",
        help_text="The contributor who wrote this problem.",
    )
    title = models.CharField(max_length=200, help_text="Short title for the proposal.")
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
    archived = models.BooleanField(
        default=False,
        help_text="Hide this problem from the active list (staff-visible only).",
    )
    upvotes = models.ManyToManyField(
        OIMEContributor,
        related_name="upvoted_proposals",
        blank=True,
        help_text="Contributors who have upvoted this problem after solving it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        subject = self.get_subject_display()  # type: ignore[attr-defined]
        return f"{subject} D{self.difficulty} by {self.author}"

    def get_absolute_url(self) -> str:
        return reverse("oime-proposal-detail", args=[self.pk])

    @property
    def label(self) -> str:
        return f"{self.subject}{self.pk}"

    @property
    def time_limit_minutes(self) -> int:
        return 5 * self.difficulty + 5


class OIMEFight(models.Model):
    ANSWER_LIMIT = 5

    STATUS_CHOICES = [
        ("OIME_TBD", "In Progress"),
        ("OIME_OK", "Solved"),
        ("OIME_FAIL", "Gave Up"),
        ("OIME_TLE", "Time Limit Exceeded"),
        ("OIME_ALE", "Answer Limit Exceeded"),
    ]

    contributor = models.ForeignKey(
        OIMEContributor,
        on_delete=models.CASCADE,
        related_name="fights",
    )
    proposal = models.ForeignKey(
        OIMEProposal,
        on_delete=models.CASCADE,
        related_name="fights",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="OIME_TBD")
    wrong_answers = models.IntegerField(default=0)
    solve_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Only set when status is OIME_OK.",
    )

    class Meta:
        unique_together = [("contributor", "proposal")]

    def __str__(self) -> str:
        return f"{self.contributor} on {self.proposal}"

    @property
    def is_complete(self) -> bool:
        return self.status != "OIME_TBD"

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
        OIMEContributor,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    proposal = models.ForeignKey(
        OIMEProposal,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.proposal}"
