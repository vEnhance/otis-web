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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    main_url = models.URLField(help_text="Main URL for viewing the proposals.")
    join_url = models.URLField(help_text="URL for joining.", blank=True)

    def __str__(self) -> str:
        return self.display_name

    @property
    def has_join_url(self) -> bool:
        return self.join_url != ""

    def get_absolute_url(self) -> str:
        return self.main_url


class JoinRecord(models.Model):
    user = models.ForeignKey(
        User, help_text="The user who joined.", on_delete=models.CASCADE
    )
    tube = models.ForeignKey(
        Tube, help_text="The tube the user joined.", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(
        default=True, help_text="Set to False if things go wrong"
    )
