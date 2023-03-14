from django.db import models
from django.utils import timezone


class OpalHunt(models.Model):
    name = models.CharField(max_length=128, help_text="Display name for this hunt")
    slug = models.SlugField(max_length=32)

    active = models.BooleanField(
        help_text="Whether to highlight this hunt on the list.",
        default=True,
    )
    start_date = models.DateTimeField(help_text="When the hunt begins.")

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

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return "#"  # TO BE IMPLEMENTED

    def has_started(self) -> bool:
        return timezone.now() >= self.start_date

    def author_signups_are_open(self) -> bool:
        if self.author_signup_deadline is None:
            return bool(self.author_signup_url)
        else:
            return timezone.now() <= self.author_signup_deadline
