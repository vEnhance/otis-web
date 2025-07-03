import os
import string
from hashlib import pbkdf2_hmac
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django.utils import timezone
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD
from sql_util.aggregates import Exists

from rpg.models import Achievement

ALLOWED_ANSWER_CHARACTERS = string.ascii_uppercase + string.digits


def answerize(s: str) -> str:
    return "".join(c for c in s.upper() if c in ALLOWED_ANSWER_CHARACTERS)


class LiveOpalHuntManager(models.Manager):
    def get_queryset(self) -> QuerySet["OpalHunt"]:
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .filter(
                start_date__lte=now,
                active=True,
            )
        )


class OpalAttempt(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user making the attempt"
    )
    puzzle = models.ForeignKey(
        "OpalPuzzle",
        on_delete=models.CASCADE,
        help_text="The puzzle being attempted",
    )
    is_correct = models.BooleanField(help_text="Whether the attempt was judged correct")
    is_close = models.BooleanField(
        default=False,
        help_text="Whether the attempt was in a predefined list of partial answers",
    )
    guess = models.CharField(max_length=128, help_text="The guess")
    created_at = models.DateTimeField(auto_now_add=True)
    excused = models.BooleanField(
        default=False,
        help_text="Allows admins to maker a guess as not counting towards the guess limit.",
    )

    def __str__(self):
        return f"{self.user.username} guessed {self.guess} for {self.puzzle}"

    def save(self, *args: Any, **kwargs: Any):
        self.is_correct = self.puzzle.check_guess(self.guess)
        self.is_close = self.puzzle.check_partial(self.guess)
        super().save(*args, **kwargs)


def puzzle_file_name(instance: "OpalPuzzle", filename: str) -> str:
    del filename
    hexstring = pbkdf2_hmac(
        "sha256",
        (settings.OPAL_HASH_KEY + str(instance.pk)).encode("utf-8"),
        b"salt is yummy so is sugar",
        100000,
        dklen=18,
    ).hex()
    return os.path.join("opals", instance.hunt.slug, hexstring, instance.slug + ".pdf")


class OpalPuzzle(models.Model):
    hunt = models.ForeignKey(
        "OpalHunt",
        on_delete=models.CASCADE,
        help_text="The hunt this puzzle belongs to",
    )
    title = models.CharField(max_length=128, help_text="Name of the puzzle")
    slug = models.SlugField(help_text="Slug for the puzzle")
    answer = models.CharField(
        max_length=128, help_text="Answer to the puzzle, as displayed"
    )
    partial_answers = models.TextField(
        default="",
        help_text="Comma-separated list of partial answers for the puzzle.",
        blank=True,
    )

    order = models.SmallIntegerField(
        default=0, help_text="The order to display the puzzle in within the hunt."
    )
    num_to_unlock = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of solves needed before this OPAL puzzle is unlocked",
    )
    credits = models.CharField(
        max_length=128, help_text="Credits for the author of the puzzle.", blank=True
    )

    content = models.FileField(
        upload_to=puzzle_file_name,
        verbose_name="Puzzle file",
        help_text="PDF of the puzzle you are uploading",
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        null=True,
        blank=True,
    )

    guess_limit = models.PositiveSmallIntegerField(
        default=20, help_text="Maximum number of guesses to allow"
    )
    is_metapuzzle = models.BooleanField(
        default=False, help_text="Whether this is a metapuzzle or not"
    )
    errata = models.TextField(blank=True, help_text="For announcing errata")
    hint_text = MarkdownField(
        rendered_field="hint_text_rendered",
        help_text="List of canned hints for this puzzle.",
        validator=VALIDATOR_STANDARD,
        blank=True,
    )
    hint_text_rendered = RenderedMarkdownField()

    achievement = models.ForeignKey(
        Achievement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Achievement to be awarded if this puzzle is solved",
    )

    class Meta:
        unique_together = ("hunt", "slug")
        ordering = (
            "hunt__start_date",
            "order",
            "num_to_unlock",
        )

    def __str__(self) -> str:
        return self.slug

    def get_absolute_url(self) -> str:
        return reverse("opal-show-puzzle", args=(self.hunt.slug, self.slug))

    @property
    def is_uploaded(self) -> bool:
        return bool(self.content)

    @property
    def get_attempt_log_url(self) -> str:
        return reverse("opal-attempts-list", args=(self.hunt.slug, self.slug))

    def can_view(self, user: User) -> bool:
        return (
            self.hunt.has_started and self.hunt.num_solves(user) >= self.num_to_unlock
        )

    def check_guess(self, guess: str) -> bool:
        return answerize(self.answer) == answerize(guess)

    def check_partial(self, guess: str) -> bool:
        partials = [
            answer.strip()
            for answer in self.partial_answers.split(",")
            if answer.strip()
        ]
        return any(answerize(answer) == answerize(guess) for answer in partials)

    def is_solved_by(self, user: User) -> int:
        return OpalAttempt.objects.filter(
            puzzle=self,
            user=user,
            is_correct=True,
        ).exists()


class OpalHunt(models.Model):
    name = models.CharField(max_length=128, help_text="Display name for this hunt")
    slug = models.SlugField(max_length=32, unique=True)

    active = models.BooleanField(
        help_text="Whether to highlight this hunt on the list.",
        default=True,
    )
    start_date = models.DateTimeField(help_text="When the hunt begins.")
    hints_released_date = models.DateTimeField(help_text="When to start showing hints.")

    author_signup_url = models.URLField(
        blank=True,
        help_text="Link to signup form for authors",
    )
    author_signup_deadline = models.DateTimeField(
        null=True, blank=True, help_text="Authors need to sign up by this date."
    )
    author_draft_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Authors need to have drafts of their puzzles done by this date.",
    )

    story_text = MarkdownField(
        rendered_field="story_text_rendered",
        help_text="Text to show on the round page.",
        validator=VALIDATOR_STANDARD,
        blank=True,
    )
    story_text_rendered = RenderedMarkdownField()

    objects = models.Manager()
    live = LiveOpalHuntManager()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("opal-puzzle-list", args=(self.slug,))

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start_date

    @property
    def author_signups_are_open(self) -> bool:
        if not self.author_signup_url:
            return False
        elif self.author_signup_deadline is None:
            return True
        else:
            return timezone.now() <= self.author_signup_deadline

    def num_solves(self, user: User) -> int:
        return (
            OpalPuzzle.objects.filter(hunt=self)
            .filter(
                Exists(
                    "opalattempt",
                    filter=Q(
                        user=user,
                        is_correct=True,
                    ),
                )
            )
            .count()
        )

    def get_queryset_for_user(self, user: User) -> QuerySet[OpalPuzzle]:
        return OpalPuzzle.objects.filter(hunt=self).annotate(
            unlocked=Q(num_to_unlock__lte=self.num_solves(user)),
            solved=Exists("opalattempt", filter=Q(user=user, is_correct=True)),
        )
