import os
import random
import re
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django.utils import timezone
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD

from core.models import Semester
from roster.country_abbrevs import (
    COUNTRY_CHOICES,
    get_country_flag,
    get_country_imo_url,
    get_country_name,
)

# The first IMO was held in 1959; nobody in OTIS predates that.
FIRST_IMO_YEAR = 1959

USERNAME_CHARACTERS = re.compile(r"[A-Za-z0-9._-]+")


def validate_username(value: str) -> None:
    """Checks a social media handle.

    Pasting the handle with its @ is the easy mistake to make, and it would
    silently break the profile links, so it gets its own message rather than
    the generic one about which characters are allowed."""
    if value.startswith("@"):
        raise ValidationError("Enter just the username, without the leading @.")
    if not USERNAME_CHARACTERS.fullmatch(value):
        raise ValidationError(
            "Only letters, digits, and the characters . _ - are allowed."
        )


def validate_at_most_1mb(f: File):  # type: ignore
    if f.size > 1024 * 1024:
        raise ValidationError("At most 1MB allowed")


def validate_year_list(value: str) -> None:
    """Checks a comma-separated list of plausible four-digit years."""
    if not value:
        return
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk.isdigit():
            raise ValidationError(f"{chunk} is not a year; use e.g. 2023, 2024.")
        year = int(chunk)
        if not FIRST_IMO_YEAR <= year <= timezone.now().year + 1:
            raise ValidationError(
                f"{year} is not between {FIRST_IMO_YEAR} and {timezone.now().year + 1}."
            )


def avatar_file_name(instance: "YearbookEntry", filename: str) -> str:
    del instance
    ext = os.path.splitext(filename)[-1].lower()
    n = random.randrange(0, 2**64)
    return os.path.join("yearbook", f"{n:016x}{ext}")


class YearbookEntry(models.Model):
    """An opt-in yearbook page for a single OTIS participant.

    Creating a row is the opt-in, and `is_draft` is the way back out: rather
    than offering a delete button, taking yourself out of the yearbook hides
    the page but keeps what you wrote, so that changing your mind again
    doesn't mean starting over. Real names and years of OTIS participation are
    read off the attached user rather than stored here, since the yearbook
    policy is that both of those are shown."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="yearbook_entry",
        help_text="The person this yearbook entry belongs to",
    )

    # -- Fields shown on the listing --
    tagline = models.CharField(
        max_length=64,
        blank=True,
        help_text="A short one-liner shown next to your name, at most 64 characters. "
        'For example, "just another otter".',
    )
    country = models.CharField(
        max_length=6,
        blank=True,
        choices=COUNTRY_CHOICES,
        help_text="The country you would like shown next to your name.",
    )
    graduation_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="High school graduation year",
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="The year you graduated (or expect to graduate) from high school. "
        "Leave blank to not show this.",
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        upload_to=avatar_file_name,
        help_text="A small picture of yourself, no more than 1 megabyte. "
        "It gets displayed as a square thumbnail, so a square image works best.",
        validators=[
            validate_at_most_1mb,
            FileExtensionValidator(
                allowed_extensions=["png", "jpg", "jpeg", "gif", "webp"]
            ),
        ],
    )

    # -- Fields shown only on the individual page --
    email = models.EmailField(
        blank=True,
        help_text="An email address other OTIS folks can reach you at. "
        "Leave blank to not show one.",
    )
    discord_username = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Discord username",
        validators=[validate_username],
        help_text="Your Discord handle, without the leading @.",
    )
    github_username = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="GitHub username",
        validators=[validate_username],
        help_text="Your GitHub username, without the leading @.",
    )
    aops_username = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="AoPS username",
        validators=[validate_username],
        help_text="Your Art of Problem Solving username.",
    )
    instagram_username = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Instagram username",
        validators=[validate_username],
        help_text="Your Instagram handle, without the leading @.",
    )
    imo_years = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="IMO participations",
        validators=[validate_year_list],
        help_text="Comma-separated years you competed at the IMO, e.g. 2023, 2024.",
    )
    university = models.CharField(
        max_length=128,
        blank=True,
        help_text="The university you attend or attended, if any.",
    )
    bio = MarkdownField(
        blank=True,
        rendered_field="bio_rendered",
        validator=VALIDATOR_STANDARD,
        verbose_name="Personal page",
        help_text="Write as much or as little about yourself as you'd like, in Markdown. "
        "This is the main body of your yearbook page.",
    )
    bio_rendered = RenderedMarkdownField()

    is_draft = models.BooleanField(
        default=False,
        verbose_name="Draft mode",
        help_text="While this is checked, your page is hidden from the yearbook; "
        "only you and OTIS staff can see it. Use this to draft your page before "
        "publishing it, or to quietly take yourself out of the yearbook later "
        "without losing anything you wrote.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "yearbook entry"
        verbose_name_plural = "yearbook entries"
        ordering = ("user__first_name", "user__last_name", "user__username")

    def __str__(self) -> str:
        return f"Yearbook entry for {self.user.username}"

    def get_absolute_url(self) -> str:
        return reverse("yearbook-detail", args=(self.pk,))

    def clean(self) -> None:
        super().clean()
        # Normalize the IMO years to a sorted, deduplicated, tidy list
        if self.imo_years:
            validate_year_list(self.imo_years)
            years = {int(chunk.strip()) for chunk in self.imo_years.split(",")}
            self.imo_years = ", ".join(str(year) for year in sorted(years))

    @classmethod
    def visible_to(cls, user: User) -> QuerySet["YearbookEntry"]:
        """Everything `user` is allowed to see: drafts are hidden from everyone
        except their author and staff."""
        queryset = cls.objects.select_related("user")
        if user.is_staff:
            return queryset
        return queryset.filter(Q(is_draft=False) | Q(user=user))

    @property
    def name(self) -> str:
        """The real name of the person, per yearbook policy."""
        return self.user.get_full_name() or self.user.username

    @property
    def country_name(self) -> str:
        return get_country_name(self.country) if self.country else ""

    @property
    def country_flag(self) -> str:
        return get_country_flag(self.country) if self.country else ""

    @property
    def country_imo_url(self) -> str:
        return get_country_imo_url(self.country) if self.country else ""

    @property
    def imo_year_list(self) -> list[int]:
        if not self.imo_years:
            return []
        return sorted(
            int(chunk.strip()) for chunk in self.imo_years.split(",") if chunk.strip()
        )

    @property
    def otis_semesters(self) -> QuerySet[Semester]:
        """The semesters during which this person was an OTIS student."""
        return (
            Semester.objects.filter(student__user=self.user, student__legit=True)
            .order_by("end_year")
            .distinct()
        )

    @property
    def otis_years(self) -> Optional[str]:
        """A compact range like "2021-2024", for use on the listing."""
        semesters = list(self.otis_semesters)
        if not semesters:
            return None
        return f"{semesters[0].start_year}-{semesters[-1].end_year}"
