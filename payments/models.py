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
    PREF_CHOICES = (
        ("", "Not specified"),
        ("INV", "Invoice adjustment"),
        ("PB", "Pro bono"),
        ("PPL", "PayPal"),
        ("VNM", "Venmo"),
        ("ZLL", "Zelle"),
    )

    user = models.OneToOneField(
        User,
        related_name="workers",
        on_delete=models.CASCADE,
    )
    payment_preference = models.CharField(
        max_length=3,
        choices=PREF_CHOICES,
        default='',
    )

    paypal_username = models.CharField(max_length=128)
    venmo_handle = models.CharField(max_length=128)
    zelle_info = models.CharField(max_length=128)

    notes = models.TextField(help_text="Any notes on payment or whatever.")

    def __str__(self) -> str:
        return self.user.username


class JobFolder(models.Model):
    name = models.CharField(max_length=80, help_text="A name for the folder")

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    STATUS_CHOICES = (
        ("NEW", "Open"),
        ("IP", "In progress"),
        ("PRV", "Pending review"),
        ("OK", "Completed"),
    )
    folder = models.ForeignKey(
        JobFolder,
        on_delete=models.CASCADE,
        help_text="This is the folder that the job goes under.")
    name = models.CharField(max_length=80, help_text="Name of job")
    description = models.TextField(help_text="A job description of what you should do")
    due_date = models.DateTimeField(help_text="When the job should be finished by")

    spades_bounty = models.PositiveIntegerField(help_text="How many spades the job is worth")
    usd_bounty = models.PositiveIntegerField(help_text="How many US dollars the job is worth")

    assignee = models.ForeignKey(
        Worker,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="The worker that is currently assigned.",
    )
    status = models.CharField(
        max_length=3,
        default='NEW',
        choices=STATUS_CHOICES,
        help_text='The current status of the job',
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
