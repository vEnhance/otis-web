from typing import TYPE_CHECKING, ClassVar

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


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

_ANONYMOUS_ANIMALS = [
    "Aardvark",
    "Badger",
    "Cat",
    "Dinosaur",
    "Echidna",
    "Ferret",
    "Gazelle",
    "Hedgehog",
    "Ibis",
    "Jaguar",
    "Koala",
    "Lemur",
    "Monkey",
    "Narwhal",
    "Otter",  # orangutan?
    "Pangolin",
    "Quokka",
    "Raccoon",
    "Salamander",
    "Tapir",
    "Urchin",
    "Vole",
    "Wombat",
    "Xerus",
    "Yak",
    "Zebra",
]


def _anonymous_alias(seed: int) -> str:
    """A stable ``Anonymous <Animal>`` alias derived from an integer seed."""
    return f"Anonymous {_ANONYMOUS_ANIMALS[seed % len(_ANONYMOUS_ANIMALS)]}"


class OIMEContributor(models.Model):
    """A student who participates in OIME (as proposer and/or testsolver)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="oime_contributor",
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Published name for all OIME testsolving interactions. Nicknames or usernames are fine if you prefer.",
    )
    casual_mode = models.BooleanField(
        default=False,
        help_text="If set, this contributor browses casually: they can view every problem "
        "statement untimed and upvote, nothing is recorded, and they can no longer start "
        "timed sessions. Solutions stay hidden until revealed per-problem.",
    )
    ranked_cutoff = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set each time this contributor returns to ranked mode from casual mode. "
        "Problems created at or before this time are no longer eligible for a timed solve by "
        "them (they could have browsed them casually) and stay browsable casually instead.",
    )
    revealed_proposals = models.ManyToManyField(
        "OIMEProposal",
        related_name="revealed_by",
        blank=True,
        help_text="Proposals whose solution this contributor has chosen to reveal.",
    )
    hide_from_leaderboards = models.BooleanField(
        default=False,
        help_text="If checked, your name is shown as an anonymous alias on testsolving leaderboards.",
    )
    hide_from_acknowledgments = models.BooleanField(
        default=False,
        help_text="If checked, your name is omitted of published testsolver acknowledgments in the final packet.",
    )

    def __str__(self) -> str:
        return self.display_name

    @property
    def leaderboard_name(self) -> str:
        """Name to show on testsolving leaderboards, anonymized on request."""
        if self.hide_from_leaderboards:
            return _anonymous_alias(self.pk)
        return self.display_name


class OIMEYear(models.Model):
    """One season of the OTIS Mock AIME.

    Only one model even when there's two tests. Sets the proposal window, links
    to the Overleaf project where editing happens, and records when the contest
    is released; at that point every chosen problem is retired.
    """

    display_name = models.CharField(
        max_length=128, help_text="e.g. OTIS Mock AIME 2027"
    )
    proposals_open_at = models.DateTimeField(
        help_text="Problem proposals are accepted from this moment."
    )
    proposals_close_at = models.DateTimeField(
        help_text="Problem proposals are no longer accepted from this moment."
    )
    release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the contest goes public. From this moment every selected "
        "problem (anything not deferred) is retired.",
    )
    overleaf_url = models.URLField(
        blank=True,
        help_text="The Overleaf project where selected problems are edited.",
    )

    if TYPE_CHECKING:
        selections: "RelatedManager[OIMESelection]"

    class Meta:
        ordering = ("-proposals_open_at",)

    def __str__(self) -> str:
        return self.display_name

    def get_absolute_url(self) -> str:
        return reverse("oime-year-detail", args=[self.pk])

    @classmethod
    def accepting(cls) -> "models.QuerySet[OIMEYear]":
        """Years whose proposal window contains the present moment."""
        now = timezone.now()
        return cls.objects.filter(
            proposals_open_at__lte=now, proposals_close_at__gt=now
        )


class OIMEProposal(models.Model):
    SUBJECT_CHOICES = (
        ("A", "Alg"),
        ("C", "Combo"),
        ("G", "Geo"),
        ("N", "NT"),
    )
    DIFFICULTY_CHOICES = (
        (1, "🔥 × 1 (AIME 1-3): 10 minutes"),
        (2, "🔥 × 2 (AIME 4-6): 15 minutes"),
        (3, "🔥 × 3 (AIME 7-9): 20 minutes"),
        (4, "🔥 × 4 (AIME 10-12): 25 minutes"),
        (5, "🔥 × 5 (AIME 13-15): 30 minutes"),
    )

    author = models.ForeignKey(
        OIMEContributor,
        on_delete=models.CASCADE,
        related_name="proposals",
        help_text="The contributor who wrote this problem.",
    )
    credit = models.CharField(
        max_length=200,
        blank=True,
        help_text="How you'd like this problem credited (for example, to include "
        "coauthors). Defaults to your display name.",
    )
    title = models.CharField(
        max_length=200,
        help_text="Short title for the proposal. No spoilers!",
    )
    statement = models.TextField(help_text="The problem statement, in LaTeX.")
    answer = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)],
        help_text="Integer answer (0-999).",
    )
    solution = models.TextField(help_text="Full solution write-up, in LaTeX.")
    subject = models.CharField(max_length=1, choices=SUBJECT_CHOICES)
    difficulty = models.IntegerField(
        help_text="Difficulty rating (affects testsolve time limits). CANNOT BE CHANGED AFTER SUBMISSION.",
        choices=DIFFICULTY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    archived = models.BooleanField(
        default=False,
        help_text="Hide this problem from the active list (staff-visible only).",
    )
    is_draft = models.BooleanField(
        default=False,
        verbose_name="Draft",
        help_text="Keep this problem as a private draft while you are still working "
        "on it. Drafts are hidden from everyone else and are only listed on your own "
        "drafts page; uncheck this box when it is ready for testsolving.",
    )
    upvotes = models.ManyToManyField(
        OIMEContributor,
        related_name="upvoted_proposals",
        blank=True,
        help_text="Contributors who have upvoted this problem after solving it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    if TYPE_CHECKING:
        selections: "RelatedManager[OIMESelection]"

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.label

    def get_absolute_url(self) -> str:
        return reverse("oime-proposal-detail", args=[self.pk])

    @classmethod
    def in_pool(cls) -> "models.QuerySet[OIMEProposal]":
        """Problems open for testsolving: published, not archived, not retired.

        A problem is retired once it's selected for a released contest year.
        """
        retired = OIMESelection.retiring().values("proposal_id")
        return cls.objects.filter(is_draft=False, archived=False).exclude(
            pk__in=retired
        )

    @property
    def label(self) -> str:
        return f"{self.subject}{self.pk}"

    @property
    def credit_display(self) -> str:
        """How to attribute the problem: the credit string, or the author's name."""
        return self.credit or self.author.display_name

    @property
    def difficulty_display(self) -> str:
        return f"🔥 × {self.difficulty}"

    @property
    def time_limit_minutes(self) -> int:
        return 5 * self.difficulty + 5

    @cached_property
    def is_selected(self) -> bool:
        """Chosen for some year's contest (shortlisted or further along).

        From that point the TeX repository owns the text, so the author can no
        longer edit it here. Deferred selections do not count.
        """
        return self.selections.exclude(status="SEL_DEFERRED").exists()

    @cached_property
    def is_retired(self) -> bool:
        """Chosen for a released contest."""
        return OIMESelection.retiring().filter(proposal=self).exists()

    @property
    def is_frozen(self) -> bool:
        """No new sessions, upvotes or comments: archived or retired."""
        return self.archived or self.is_retired


class OIMESelection(models.Model):
    """Verdict of one proposal for one year.

    No row means unreviewed. Deferred is reviewed and passed over, staying in
    pool for later years. Anything else means chosen; status tracks editing,
    which happens in Overleaf. The statement and solution stored here are the
    originals.
    """

    STATUS_CHOICES = (
        ("SEL_DEFERRED", "Deferred"),
        ("SEL_SHORTLISTED", "Shortlisted"),
        ("SEL_EDITING", "Editing"),
        ("SEL_REVIEW", "In review"),
        ("SEL_DONE", "Done"),
    )
    BLOCKED_ON: ClassVar[dict[str, str]] = {
        "SEL_DEFERRED": "",
        "SEL_SHORTLISTED": "EIC",
        "SEL_EDITING": "editor",
        "SEL_REVIEW": "EIC",
        "SEL_DONE": "",
    }
    year = models.ForeignKey(
        OIMEYear, on_delete=models.CASCADE, related_name="selections"
    )
    proposal = models.ForeignKey(
        OIMEProposal, on_delete=models.CASCADE, related_name="selections"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="SEL_SHORTLISTED"
    )
    editor = models.ForeignKey(
        OIMEContributor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editing",
        help_text="The contributor writing up the solution in the TeX repository.",
    )
    notes = models.TextField(blank=True, help_text="Staff-only problem notes.")
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short LaTeX description for the answer key and statistics "
        "tables, e.g. $3n$ and $4n$. Defaults to the title.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("year", "proposal"),)
        ordering = ("proposal__subject", "proposal_id")

    def __str__(self) -> str:
        return f"{self.proposal.label} for {self.year}"

    @classmethod
    def retiring(cls) -> "models.QuerySet[OIMESelection]":
        """All selections that should retire their problem."""
        return cls.objects.filter(year__release_at__lte=timezone.now()).exclude(
            status="SEL_DEFERRED"
        )

    @property
    def is_deferred(self) -> bool:
        return self.status == "SEL_DEFERRED"

    @property
    def blocked_on(self) -> str:
        return self.BLOCKED_ON[self.status]


class OIMEFight(models.Model):
    ANSWER_LIMIT = 5

    STATUS_CHOICES = (
        ("OIME_TBD", "In Progress"),
        ("OIME_OK", "Solved"),
        ("OIME_FAIL", "Gave Up"),
        ("OIME_TLE", "Time Limit Exceeded"),
        ("OIME_ALE", "Answer Limit Exceeded"),
    )

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
    wrong_answers = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = (("contributor", "proposal"),)

    def __str__(self) -> str:
        return f"{self.contributor} on {self.proposal}"

    @property
    def answer_attempts_display(self) -> str:
        return "✗" * self.wrong_answers + "·" * (self.ANSWER_LIMIT - self.wrong_answers)

    @property
    def time_display(self) -> str:
        """Fight duration as MM:SS via submitted_at − started_at. Empty for TLE and in-progress."""
        if self.submitted_at is not None and self.status != "OIME_TLE":
            seconds = int((self.submitted_at - self.started_at).total_seconds())
            m, s = divmod(seconds, 60)
            return f"{m:02d}:{s:02d}"
        return ""

    @property
    def is_complete(self) -> bool:
        return self.status != "OIME_TBD"

    @property
    def is_success(self) -> bool:
        return self.status == "OIME_OK"

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
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.proposal}"

    @property
    def is_edited(self) -> bool:
        """True only if the comment was meaningfully edited after creation."""
        return (self.updated_at - self.created_at).total_seconds() > 60
