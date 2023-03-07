from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse

from core.models import Unit


class ProblemSuggestion(models.Model):
    STATUS_CHOICES = (
        ("SUGG_EDIT", "Edits requested"),
        ("SUGG_NEW", "Pending"),
        ("SUGG_NOK", "Nice rejection"),  # processed but given spades, not used though
        ("SUGG_OK", "Accepted"),
        ("SUGG_REJ", "Rejected"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="User who suggested the problem.",
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, help_text="The unit to suggest the problem for."
    )
    weight = models.PositiveSmallIntegerField(
        choices=((2, 2), (3, 3), (5, 5), (9, 9)), null=True, blank=True
    )
    source = models.CharField(
        max_length=60, help_text="Source of the problem, e.g. `Shortlist 2018 A7`."
    )
    description = models.CharField(
        max_length=100,
        help_text="A one-line summary of problem, e.g. `Inequality with cube roots`.",
    )
    hyperlink = models.URLField(
        help_text="A hyperlink if appropriate, e.g. AoPS thread. "
        "Required if the problem is on AoPS.",
        blank=True,
    )
    statement = models.TextField(help_text="Statement of the problem, in LaTeX.")
    solution = models.TextField(help_text="Solution to the problem, in LaTeX.")
    comments = models.TextField(help_text="Any extra comments.", blank=True)
    acknowledge = models.BooleanField(
        help_text="Acknowledge me for this contribution. "
        "(Uncheck for an anonymous contribution.)",
        default=True,
    )
    staff_comments = models.TextField(
        help_text="Comments by Evan on this suggestion",
        blank=True,
    )

    status = models.CharField(
        max_length=10,
        default="SUGG_NEW",
        choices=STATUS_CHOICES,
        help_text="The current status of the suggestion",
    )

    eligible = models.BooleanField(
        default=True, help_text="Whether this suggestion is eligible for spades."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_problemsuggestion"  # historical babbage

    def __str__(self) -> str:
        return self.description

    def get_absolute_url(self) -> str:
        return reverse("suggest-update", args=(self.pk,))
