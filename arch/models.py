from pathlib import Path
from typing import Optional

import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.db.models.manager import Manager
from django.urls import reverse

User = get_user_model()


def get_disk_statement_from_puid(puid: str) -> Optional[str]:
    if settings.PATH_STATEMENT_ON_DISK is None:
        return None
    statement_path = Path(settings.PATH_STATEMENT_ON_DISK) / f"{puid}.html"
    if statement_path.exists() and statement_path.is_file():
        return statement_path.read_text()
    return None


# Create your models here.
@reversion.register()
class Problem(models.Model):
    puid = models.CharField(
        max_length=20,
        help_text="Problem identifier, as printed in OTIS. Capital letters and digits only.",
        unique=True,
        verbose_name="PUID",
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9]+$",
                message="Only uppercase letters and digits appear in PUID's.",
            )
        ],
    )
    hyperlink = models.URLField(help_text="An AoPS URL or similar", blank=True)
    vote_set: Manager["Vote"]

    class Meta:
        ordering = ("puid",)

    def __str__(self) -> str:
        return self.puid

    def get_absolute_url(self):
        return reverse("hint-list", args=(self.puid,))

    def get_statement(self) -> Optional[str]:
        return get_disk_statement_from_puid(self.puid)

    @property
    def niceness(self) -> Optional[float]:
        votes: models.QuerySet[Vote] = self.vote_set.all()
        if len(votes) > 0:
            return round(sum(vote.niceness for vote in votes) / len(votes), 2)
        else:
            return None


class Vote(models.Model):
    user = models.ForeignKey(
        User,
        help_text="User who voted for this problem.",
        on_delete=models.CASCADE,
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        help_text="The container of the current vote.",
    )
    niceness = models.PositiveIntegerField(
        help_text="A student submitted number from 0 to 10 used to indicate "
        "the approximate niceness of a problem.",
        validators=[MaxValueValidator(10)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


@reversion.register()
class Hint(models.Model):
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        help_text=r"The container of the current hint.",
    )
    keywords = models.CharField(
        max_length=255,
        default="",
        blank=True,
        help_text=r"A comma-separated list of keywords that a solver could look at "
        "to help them guess whether the hint is relevant or not. "
        "These are viewable immediately, so no spoilers here. "
        "Examples are 'setup', 'advice', 'answer confirmation', 'nudge',"
        "'main idea', 'solution set', 'converse direction', 'construction', etc. "
        "Not all hints go well with keywords, so you can leave this "
        "blank if you can't think of anything useful to write.",
    )
    number = models.PositiveIntegerField(
        help_text=r"A number from 0 to 100 used to indicate an "
        r"ordering for the hints. "
        r"Here a number 0 means a hint given to someone at the very start "
        r"whereas 100 means a hint given to someone who was read all previous hints "
        r"or is close to the end of the problem. "
        r"Do your best to make up an extrapolation for everything in between. "
        r"A good idea is to give a sequence of hints with nearby numbers, say 20/21/22, "
        r"each of which elaborates on the previous hint."
    )
    content = models.TextField(
        help_text="The content of the hint. LaTeX rendering is okay."
    )

    class Meta:
        unique_together = (
            "problem",
            "number",
        )

    def __str__(self):
        return f"Hint {self.number}% for {self.problem}"

    def get_absolute_url(self):
        return reverse(
            "hint-detail",
            args=(
                self.problem.puid,
                self.number,
            ),
        )

    @property
    def puid(self) -> str:
        return self.problem.puid
