from core.models import Semester
from django.contrib.auth.models import User
from django.db import models
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
    user = models.OneToOneField(
        User,
        related_name="workers",
        on_delete=models.CASCADE,
    )

    paypal_username = models.CharField(max_length=128, blank=True)
    venmo_handle = models.CharField(max_length=128, blank=True)
    zelle_info = models.CharField(max_length=128, blank=True)

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
    description = models.TextField(help_text="About this folder", blank=True)
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    STATUS_CHOICES = (
        ("NEW", "Open"),
        ("IP", "In progress"),
        ("PRV", "Pending review"),
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
    description = models.TextField(
        help_text="A job description of what you should do",
        blank=True,
    )
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

    status = models.CharField(
        max_length=3,
        default='NEW',
        choices=STATUS_CHOICES,
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
        help_text="The worker that is currently assigned.",
    )
    worker_deliverable = models.TextField(
        blank=True,
        help_text="The worker can submit some deliverable here",
    )
    worker_notes = models.TextField(
        blank=True,
        help_text="The worker can make some notes here",
    )

    def __str__(self) -> str:
        return self.name
