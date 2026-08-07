from typing import TYPE_CHECKING, Optional

import reversion
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.db.models.manager import Manager
from django.urls import reverse

from arch.utils import get_disk_statement_from_puid

if TYPE_CHECKING:
    assert hasattr(reversion, "register")


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

    def get_html_statement(self) -> Optional[str]:
        return get_disk_statement_from_puid(self.puid, "html")

    def get_tex_statement(self) -> Optional[str]:
        return get_disk_statement_from_puid(self.puid, "tex")

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

    def __str__(self) -> str:
        return f"{self.user.username} vote for {self.problem}"


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
