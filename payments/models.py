from core.models import Semester
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
        return self.created_at.strftime('%c')


class Worker(models.Model):
    RE_EMAIL = r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)'
    RE_PHONE = r'^[0-9()+-]+'
    RE_AT_USER = r'@[-a-zA-Z0-9_]+'

    user = models.OneToOneField(
        User,
        related_name="workers",
        on_delete=models.CASCADE,
    )

    paypal_username = models.CharField(
        max_length=128,
        blank=True,
        help_text="Input a @username, email, or mobile",
        validators=[RegexValidator(f'^({RE_AT_USER}|{RE_EMAIL}|{RE_PHONE})$')],
    )
    venmo_handle = models.CharField(
        max_length=128,
        blank=True,
        help_text="Must start with leading @",
        validators=[RegexValidator(f'^{RE_AT_USER}$')],
    )
    zelle_info = models.CharField(
        max_length=128,
        blank=True,
        help_text="Either email or mobile",
        validators=[RegexValidator(f'^({RE_AT_USER}|{RE_PHONE})$')],
    )

    google_username = models.CharField(
        max_length=128,
        blank=True,
        help_text="For e.g. sharing with Google Drive, etc. "
        "Do not include @gmail.com or @google.com.",
        validators=[RegexValidator(r"^[-a-zA-Z0-9_'.]+$")],
    )

    notes = models.TextField(
        help_text="Any notes on payment or whatever.",
        blank=True,
    )

    def __str__(self) -> str:
        return self.user.username


class JobFolder(models.Model):
    name = models.CharField(max_length=80, help_text="A name for the folder")
    slug = models.SlugField(help_text="A slug for this job folder")
    visible = models.BooleanField(default=True, help_text="Whether to show this folder")
    description = MarkdownField(
        rendered_field='description_rendered',
        help_text="Instructions and so on for this folder.",
        validator=VALIDATOR_STANDARD,
        blank=True)
    description_rendered = RenderedMarkdownField()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse('job-list', args=(self.slug,))


class Job(models.Model):
    PROGRESS_CHOICES = (
        ("NEW", "In Progress"),
        ("SUB", "Submitted"),
        ("OK", "Completed"),
    )
    PREF_CHOICES = (
        ("", "Not specified"),
        ("INV", "Invoice adjustment"),
        ("PB", "Pro bono"),
        ("PPL", "PayPal"),
        ("VNM", "Venmo"),
        ("ZLL", "Zelle"),
    )

    folder = models.ForeignKey(
        JobFolder,
        on_delete=models.CASCADE,
        help_text="This is the folder that the job goes under.")
    name = models.CharField(max_length=80, help_text="Name of job")

    description = MarkdownField(
        rendered_field='description_rendered',
        help_text="Instructions and so on for this particular job.",
        validator=VALIDATOR_STANDARD,
        blank=True)
    description_rendered = RenderedMarkdownField()

    due_date = models.DateTimeField(
        help_text="When the job should be finished by",
        null=True,
        blank=True,
    )

    spades_bounty = models.PositiveIntegerField(
        help_text="How many spades the job is worth",
        default=0,
    )
    usd_bounty = models.PositiveIntegerField(
        help_text="How many US dollars the job is worth",
        default=0,
    )

    progress = models.CharField(
        max_length=3,
        default='NEW',
        choices=PROGRESS_CHOICES,
        help_text='The current status of the job',
    )
    payment_preference = models.CharField(
        max_length=3,
        choices=PREF_CHOICES,
        default='',
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse('job-detail', args=(self.pk,))

    @property
    def status(self) -> str:
        if self.assignee is None:
            return "Open"
        else:
            return self.get_progress_display()  # type: ignore
