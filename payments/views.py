import logging
from typing import Any

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models.aggregates import Count, Sum
from django.db.models.expressions import F
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.forms.models import BaseModelForm
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from sql_util.aggregates import SubqueryCount, SubqueryMax, SubqueryMin
from sql_util.utils import Exists

from otisweb.decorators import verified_required
from otisweb.mixins import AdminRequiredMixin, VerifiedRequiredMixin
from payments.models import Job, JobFolder
from roster.models import Invoice, Student

from .models import PaymentLog, Worker

logger = logging.getLogger(__name__)


def invoice(request: HttpRequest, student_pk: int, checksum: str) -> HttpResponse:
    student = get_object_or_404(Student, pk=student_pk)

    if checksum != student.get_checksum(settings.INVOICE_HASH_KEY):
        raise PermissionDenied("Bad hash provided")
    try:
        invoice = student.invoice
    except ObjectDoesNotExist:
        raise Http404("No invoice exists for this student")
    context = {
        "title": f"Payment for {student.name}",
        "student": student,
        "invoice": invoice,
        "checksum": checksum,
    }
    return render(request, "payments/invoice.html", context)


@csrf_exempt
def config(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return HttpResponseForbidden("Need to use request method GET")
    stripe_config = {"publicKey": settings.STRIPE_PUBLISHABLE_KEY}
    return JsonResponse(stripe_config, safe=False)


@csrf_exempt
def checkout(
    request: HttpRequest, invoice_pk: int, amount: int, checksum: str
) -> HttpResponse:
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    if checksum != invoice.student.get_checksum(settings.INVOICE_HASH_KEY):
        raise PermissionDenied("Bad hash provided")
    if amount <= 0:
        raise PermissionDenied("Need to enter a positive amount for payment...")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if request.method == "GET":
        domain_url = (
            "https://otis.evanchen.cc"
            if settings.PRODUCTION
            else "http://127.0.0.1:8000"
        )
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=invoice_pk,
            success_url=f"{domain_url}/payments/success/",
            cancel_url=f"{domain_url}/payments/cancelled/",
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "name": "OTIS Payment",
                    "quantity": 1,
                    "currency": "usd",
                    "amount": amount * 100,
                }
            ],
        )
        return JsonResponse({"sessionId": checkout_session["id"]})  # type: ignore
    else:
        return HttpResponseForbidden("Need to use request method GET")


# Stripe events that mean money went back to the payer. A dispute is reported
# both when it is opened and when the funds actually leave the account; both are
# listened for, and process_reversal() makes sure the second one is a no-op.
REVERSAL_EVENT_TYPES = (
    "charge.refunded",
    "charge.dispute.created",
    "charge.dispute.funds_withdrawn",
)


def cents_to_usd(cents: int) -> int:
    """Stripe reports amounts in cents, but invoices are tracked in whole dollars."""
    return int(cents) // 100


def process_payment(amount: int, invoice: Invoice, stripe_id: str = "") -> PaymentLog:
    """Credit `amount` dollars to `invoice` and log it.

    A `stripe_id` (the payment intent) is credited at most once, no matter how
    many times Stripe delivers the event for it; the existing log is returned
    unchanged in that case. Payments entered by hand carry no payment intent and
    are always credited.
    """
    with transaction.atomic():
        if stripe_id:
            # Hold the invoice for the rest of the transaction, so that two
            # deliveries of one event arriving together can't both find nothing
            # and credit it twice. MySQL has no partial unique indexes, so the
            # constraint on PaymentLog doesn't catch that race in production.
            Invoice.objects.select_for_update().get(pk=invoice.pk)
            credited = PaymentLog.objects.filter(
                stripe_id=stripe_id, amount__gt=0
            ).first()
            if credited is not None:
                logger.warning(f"Payment intent {stripe_id} was already credited")
                return credited
        payment_log = PaymentLog.objects.create(
            amount=amount, invoice=invoice, stripe_id=stripe_id
        )
        # F() rather than a read-modify-write, so that two payments landing at
        # the same time can't clobber each other's credit
        Invoice.objects.filter(pk=invoice.pk).update(
            total_paid=F("total_paid") + amount
        )
        invoice.refresh_from_db(fields=("total_paid",))
    return payment_log


def process_reversal(stripe_id: str, cents_reversed: int) -> PaymentLog | None:
    """Take back credit for the payment intent `stripe_id`.

    `cents_reversed` is the total Stripe has taken back for that payment so far,
    which is how Stripe reports both refunds and disputes. Only the part that
    hasn't been taken back yet is reversed, so redelivered events and a dispute
    that arrives twice change nothing, and a series of partial refunds never
    reverses more than was paid.

    The reversal is recorded as its own log with a negative amount rather than by
    editing the original, so the payment history stays auditable. Returns that
    log, or None if there was nothing left to reverse.
    """
    with transaction.atomic():
        try:
            payment_log = PaymentLog.objects.select_for_update().get(
                stripe_id=stripe_id, amount__gt=0
            )
        except PaymentLog.DoesNotExist:
            logger.warning(f"Stripe reversed unknown payment intent {stripe_id}")
            return None

        reversed_so_far = -(
            PaymentLog.objects.filter(stripe_id=stripe_id, amount__lt=0).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        amount = min(cents_to_usd(cents_reversed), payment_log.amount) - reversed_so_far
        if amount <= 0:
            return None

        invoice = payment_log.invoice
        reversal = PaymentLog.objects.create(
            amount=-amount,
            invoice=invoice,
            stripe_id=stripe_id,
        )
        Invoice.objects.filter(pk=invoice.pk).update(
            total_paid=F("total_paid") - amount
        )
        if reversed_so_far + amount >= payment_log.amount:
            # Nothing of this payment is left. Flag the payment and its reversals
            # alike, since totals over PaymentLog skip refunded rows and would
            # otherwise subtract the reversals a second time.
            PaymentLog.objects.filter(stripe_id=stripe_id).update(refunded=True)
            reversal.refunded = True
        logger.warning(f"Reversed ${amount} of payment intent {stripe_id}")
    return reversal


@csrf_exempt
def webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseForbidden("Need to use request method POST")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body
    if "HTTP_STRIPE_SIGNATURE" not in request.META:
        if settings.PRODUCTION:
            logger.error(f"No HTTP_STRIPE_SIGNATURE in request.META = {request.META}")
        return HttpResponse(status=400)
    sig_header: str = request.META["HTTP_STRIPE_SIGNATURE"]
    # logger.debug(payload)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # Invalid payload
        if settings.PRODUCTION:
            logger.error(f"Invalid payload for {e!s}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:  # type: ignore
        # Invalid signature
        if settings.PRODUCTION:
            logger.error(f"Invalid signature for {e!s}")
        return HttpResponse(status=400)

    logger.debug(event)
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        process_payment(
            amount=cents_to_usd(obj["amount_total"]),
            invoice=get_object_or_404(Invoice, pk=int(obj["client_reference_id"])),
            stripe_id=obj["payment_intent"],
        )
    elif event["type"] in REVERSAL_EVENT_TYPES:
        # A refund reports the running total refunded on the charge, while a
        # dispute reports the amount being taken away.
        cents_reversed = (
            obj["amount_refunded"]
            if event["type"] == "charge.refunded"
            else obj["amount"]
        )
        stripe_id = obj.get("payment_intent")
        if stripe_id:
            process_reversal(stripe_id=stripe_id, cents_reversed=cents_reversed)
        else:
            logger.error(f"{event['type']} without a payment intent: {obj}")
    return HttpResponse(status=200)


def success(request: HttpRequest) -> HttpResponse:
    return render(request, "payments/success.html")


def cancelled(request: HttpRequest) -> HttpResponse:
    return HttpResponse("Cancelled payment")


class WorkerDetail(LoginRequiredMixin, DetailView[Worker]):
    model = Worker
    context_object_name = "worker"
    template_name = "payments/worker_detail.html"

    def get_object(self):
        worker, _ = Worker.objects.get_or_create(user=self.request.user)
        return worker


class WorkerUpdate(VerifiedRequiredMixin, UpdateView[Worker, BaseModelForm[Worker]]):
    model = Worker
    context_object_name = "worker"
    template_name = "payments/worker_form.html"
    fields = (
        "gmail_address",
        "twitch_username",
        "notes",
        "paypal_username",
        "venmo_handle",
        "zelle_info",
    )

    def get_object(self):
        worker, _ = Worker.objects.get_or_create(user=self.request.user)
        return worker

    def get_success_url(self) -> str:
        return reverse("worker-detail")


class JobFolderList(VerifiedRequiredMixin, ListView[JobFolder]):
    model = JobFolder
    context_object_name = "jobfolders"

    def get_queryset(self) -> QuerySet[JobFolder]:
        return (
            JobFolder.objects.filter(visible=True)
            .annotate(
                num_open=Count("job", filter=Q(job__assignee__isnull=True)),
                num_claimed=Count(
                    "job",
                    filter=Q(
                        job__assignee__isnull=False,
                        job__progress="JOB_NEW",
                    )
                    | Q(
                        job__assignee__isnull=False,
                        job__progress="JOB_SUB",
                    )
                    | Q(
                        job__assignee__isnull=False,
                        job__progress="JOB_REV",
                    ),
                ),
                num_done=Count("job", filter=Q(job__progress="JOB_VFD")),
            )
            .order_by("archived", "name")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        assert isinstance(self.request.user, User)
        try:
            context["worker"] = Worker.objects.get(user=self.request.user)
        except Worker.DoesNotExist:
            context["worker"] = None
        return context


class JobList(VerifiedRequiredMixin, ListView[Job]):
    model = Job
    context_object_name = "jobs"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.jobfolder = get_object_or_404(
            JobFolder, slug=self.kwargs["jobfolder_slug"]
        )

    def get_queryset(self) -> QuerySet[Job]:
        return (
            Job.objects.filter(folder=self.jobfolder)
            .annotate(assignee_count=Count("assignee"))
            .order_by(
                "assignee_count",
                "progress",
                "name",
            )
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["jobfolder"] = self.jobfolder
        return context


class JobDetail(VerifiedRequiredMixin, DetailView[Job]):
    model = Job
    context_object_name = "job"


@login_required
@verified_required
def job_claim(request: HttpRequest, pk: int) -> HttpResponse:
    assert isinstance(request.user, User)
    try:
        worker: Worker = Worker.objects.get(user=request.user)
    except Worker.DoesNotExist:
        messages.error(request, "You need to set up a work profile first")
        return HttpResponseRedirect(reverse("worker-update"))
    else:
        job: Job = Job.objects.get(pk=pk)
        jobfolder: JobFolder = job.folder
        jobs_already_claimed = Job.objects.filter(folder=jobfolder, assignee=worker)

        if job.assignee is not None:
            messages.error(request, "This task is already claimed.")
        elif (
            jobfolder.max_pending is not None
            and jobs_already_claimed.exclude(progress="JOB_VFD").count()
            >= jobfolder.max_pending
        ):
            messages.error(
                request,
                "You already reached the maximum number of pending tasks for this category.",
            )
        elif (
            jobfolder.max_total is not None
            and jobs_already_claimed.count() >= jobfolder.max_total
        ):
            messages.error(
                request,
                "You already reached the maximum number of total tasks for this category.",
            )
        else:
            job.assignee = worker
            job.save()
            messages.success(request, f"You have successfully claimed task #{job.pk}.")
        return HttpResponseRedirect(job.get_absolute_url())


class JobUpdate(VerifiedRequiredMixin, UpdateView[Job, BaseModelForm[Job]]):
    model = Job
    context_object_name = "job"
    template_name = "payments/job_form.html"
    fields = (
        "payment_preference",
        "hours_estimate",
        "worker_deliverable",
        "worker_notes",
    )

    def get_object(self, queryset: QuerySet[Job] | None = None) -> Job:
        # This check needs to happen in get_object() rather than post() so that it
        # guards GET requests too (the form leaks the assignee's submission) and so
        # that it runs *before* any changes are written to the database.
        job = super().get_object(queryset)
        if job.assignee is None:
            raise PermissionDenied("Someone needs to claim this job first.")
        elif self.request.user != job.assignee.user:
            raise PermissionDenied("Can't submit for someone else's claim.")
        elif job.progress == "JOB_VFD":
            raise PermissionDenied("This job is already completed.")
        return job

    def form_valid(self, form: BaseModelForm[Job]):
        self.object.progress = "JOB_SUB"
        messages.success(self.request, "Successfully submitted.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class InactiveWorkerList(AdminRequiredMixin, ListView[Worker]):
    model = Worker
    context_object_name = "workers"
    template_name: str = "payments/inactive_worker_list.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.jobfolder = get_object_or_404(
            JobFolder, slug=self.kwargs["jobfolder_slug"]
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["jobfolder"] = self.jobfolder
        return context

    def get_queryset(self) -> QuerySet[Worker]:
        folder = self.jobfolder
        STATUSES = ("JOB_NEW", "JOB_REV")

        queryset = Worker.objects.filter(
            Exists("job", filter=Q(progress__in=STATUSES, folder=folder))
        )
        queryset = queryset.annotate(
            latest_update=SubqueryMax("job__updated_at", filter=Q(folder=folder)),
            oldest_undone=SubqueryMin(
                "job__updated_at",
                filter=Q(progress__in=STATUSES, folder=folder),
            ),
            num_completed=SubqueryCount(
                "job",
                filter=Q(progress="JOB_VFD", folder=folder),
            ),
            num_total=SubqueryCount("job", filter=Q(folder=folder)),
        )
        queryset = queryset.order_by("latest_update", "oldest_undone")
        queryset = queryset.select_related("user")

        return queryset
