from decimal import Decimal

from core.models import Semester
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.aggregates import Sum
from django.db.models.expressions import OuterRef
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD
from roster.models import Invoice
from sql_util.aggregates import Subquery, SubquerySum


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

    max_pending = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of pending tasks that can be claimed "
        "total by one person.")
    max_total = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of tasks that can be claimed "
        "total by one person, including completed ones.")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse('job-list', args=(self.slug,))


class Job(models.Model):
    PROGRESS_CHOICES = (
        ("NEW", "In progress"),
        ("REV", "Revisions requested"),
        ("SUB", "Submitted"),
        ("VFD", "Completed"),
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
    usd_bounty = models.DecimalField(
        max_digits=8,
        decimal_places=2,
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

    @property
    def assignee_name(self) -> str:
        if self.assignee is None:
            return ""
        else:
            return self.assignee.user.get_full_name()

    @property
    def assignee_email(self) -> str:
        if self.assignee is None:
            return ""
        else:
            return self.assignee.user.email


def get_semester_invoices_with_annotations(semester: Semester) -> QuerySet[Invoice]:
    job_subquery = Job.objects.filter(
        assignee__user=OuterRef('student__user'),
        semester=semester,
        progress='VFD',
        payment_preference='INV',
    ).order_by().values('assignee__user').annotate(total=Sum('usd_bounty')).values('total')

    return Invoice.objects.filter(student__semester=semester).annotate(
        stripe_total=Coalesce(SubquerySum('paymentlog__amount'), 0),
        job_total=Coalesce(Subquery(job_subquery), Decimal(0)),
    )
