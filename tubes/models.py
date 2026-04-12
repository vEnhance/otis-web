from django.contrib.auth.models import User
from django.db import models


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
