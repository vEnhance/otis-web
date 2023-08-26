from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD

from roster.models import Invoice


class PaymentLog(models.Model):
    amount = models.IntegerField(help_text="Amount paid")
    created_at = models.DateTimeField(auto_now_add=True)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        help_text="The invoice this contributes towards",
    )

    def __str__(self) -> str:
        return self.created_at.strftime("%c")


class Worker(models.Model):
    RE_EMAIL = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    RE_PHONE = r"^[0-9()+-]+"
    RE_AT_USER = r"@[-a-zA-Z0-9_]+"

    user = models.OneToOneField(
        User,
        related_name="workers",
        on_delete=models.CASCADE,
    )

    paypal_username = models.CharField(
        max_length=128,
        blank=True,
        help_text="Input a @username, email, or mobile",
        validators=[RegexValidator(f"^({RE_AT_USER}|{RE_EMAIL}|{RE_PHONE})$")],
    )
    venmo_handle = models.CharField(
        max_length=128,
        blank=True,
        help_text="Must start with leading @",
        validators=[RegexValidator(f"^{RE_AT_USER}$")],
    )
    zelle_info = models.CharField(
        max_length=128,
        blank=True,
        help_text="Either email or mobile",
        validators=[RegexValidator(f"^({RE_AT_USER}|{RE_EMAIL}|{RE_PHONE})$")],
    )

    gmail_address = models.CharField(
        max_length=128,
        blank=True,
        help_text="Should be of the form username@gmail.com.",
        validators=[RegexValidator(r"^[-a-zA-Z0-9_'.]+@gmail\.com$")],
    )
    twitch_username = models.CharField(
        max_length=128,
        blank=True,
        help_text="Username on Twitch.tv",
        validators=[RegexValidator(r"^[-a-zA-Z0-9_'.]+$")],
    )

    notes = models.TextField(
        help_text="Any notes on payment or whatever.",
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.user.username

    @property
    def full_name(self) -> str:
        return self.user.get_full_name()

    @property
    def email(self) -> str:
        return self.user.email


class JobFolder(models.Model):
    name = models.CharField(max_length=80, help_text="A name for the folder")
    slug = models.SlugField(help_text="A slug for this job folder")
    visible = models.BooleanField(default=True, help_text="Whether to show this folder")
    archived = models.BooleanField(
        default=False, help_text="Set to True when this folder is all done."
    )
    description = MarkdownField(
        rendered_field="description_rendered",
        help_text="Instructions and so on for this folder.",
        validator=VALIDATOR_STANDARD,
        blank=True,
    )
    description_rendered = RenderedMarkdownField()

    max_pending = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of pending tasks that can be claimed "
        "total by one person.",
    )
    max_total = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of tasks that can be claimed "
        "total by one person, including completed ones.",
    )

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("job-list", args=(self.slug,))


class Job(models.Model):
    PROGRESS_CHOICES = (
        ("JOB_NEW", "Not submitted"),
        ("JOB_REV", "Revisions requested"),
        ("JOB_SUB", "Submitted"),
        ("JOB_VFD", "Completed"),
    )
    PREF_CHOICES = (
        ("PREF_NONE", "Not specified"),
        ("PREF_INVCRD", "Invoice credits"),
        ("PREF_PROBONO", "Pro bono"),
        ("PREF_PAYPAL", "PayPal"),
        ("PREF_VENMO", "Venmo"),
        ("PREF_ZELLE", "Zelle"),
    )

    folder = models.ForeignKey(
        JobFolder,
        on_delete=models.CASCADE,
        help_text="This is the folder that the job goes under.",
    )
    name = models.CharField(max_length=160, help_text="Name of job")

    description = MarkdownField(
        rendered_field="description_rendered",
        help_text="Instructions and so on for this particular job.",
        validator=VALIDATOR_STANDARD,
        blank=True,
    )
    description_rendered = RenderedMarkdownField()

    spades_bounty = models.PositiveIntegerField(
        verbose_name="♠",
        help_text="How many spades the job is worth",
        default=0,
    )
    usd_bounty = models.DecimalField(
        verbose_name="$",
        max_digits=8,
        decimal_places=2,
        help_text="How many US dollars the job is worth",
        default=0,
    )

    progress = models.CharField(
        max_length=8,
        default="JOB_NEW",
        choices=PROGRESS_CHOICES,
        help_text="The current status of the job",
    )
    hours_estimate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Optional estimate for how number of hours this took. "
        "Has no effect on your payment, but useful for me to know "
        "to make sure I'm not underpaying people broadly speaking. "
        "Decimal numbers are allowed.",
        null=True,
        blank=True,
    )

    payment_preference = models.CharField(
        max_length=15,
        choices=PREF_CHOICES,
        default="",
        blank=True,
    )
    assignee = models.ForeignKey(
        Worker,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Who is currently assigned",
    )

    worker_deliverable = models.TextField(
        blank=True,
        help_text="Enter the deliverable of the job here",
    )
    worker_notes = models.TextField(
        blank=True,
        help_text="Make any notes here",
    )

    admin_notes = models.TextField(
        blank=True,
        help_text="Evan can make internal notes here",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("job-detail", args=(self.pk,))

    @property
    def status(self) -> str:
        if self.assignee is None:
            return "Open"
        elif self.progress == "JOB_NEW":
            return "In progress"
        else:
            return self.get_progress_display()  # type: ignore

    @property
    def assignee_name(self) -> str:
        return "" if self.assignee is None else self.assignee.user.get_full_name()

    @property
    def assignee_email(self) -> str:
        return "" if self.assignee is None else self.assignee.user.email
