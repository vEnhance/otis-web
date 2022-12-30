import logging
from typing import Any, Dict

import stripe
from core.models import Semester
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied  # NOQA
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.forms.models import BaseModelForm
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)  # NOQA
from django.http.response import HttpResponseRedirect, JsonResponse  # NOQA
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from django.views.generic.list import ListView
from roster.models import Invoice, Student

from payments.models import Job, JobFolder

from .models import PaymentLog, Worker


def invoice(request: HttpRequest, student_pk: int, checksum: str) -> HttpResponse:
    student = get_object_or_404(Student, pk=student_pk)

    if checksum != student.get_checksum(settings.INVOICE_HASH_KEY):
        raise PermissionDenied("Bad hash provided")
    try:
        invoice = student.invoice
    except ObjectDoesNotExist:
        raise Http404("No invoice exists for this student")
    context = {
        "title": "Payment for " + student.name,
        "student": student,
        "invoice": invoice,
        "checksum": checksum,
    }
    return render(request, "payments/invoice.html", context)


@csrf_exempt
def config(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        stripe_config = {"publicKey": settings.STRIPE_PUBLISHABLE_KEY}
        return JsonResponse(stripe_config, safe=False)
    else:
        return HttpResponseForbidden("Need to use request method GET")


@csrf_exempt
def checkout(request: HttpRequest, invoice_pk: int, amount: int) -> HttpResponse:
    if amount <= 0:
        raise PermissionDenied("Need to enter a positive amount for payment...")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if settings.PRODUCTION:
        domain_url = "https://otis.evanchen.cc"
    else:
        domain_url = "http://127.0.0.1:8000"
    if request.method == "GET":
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=invoice_pk,
            success_url=domain_url + "/payments/success/",
            cancel_url=domain_url + "/payments/cancelled/",
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
        return JsonResponse({"sessionId": checkout_session["id"]})
    else:
        return HttpResponseForbidden("Need to use request method GET")


def process_payment(amount: int, invoice: Invoice):
    invoice.total_paid += amount
    invoice.save()
    payment_log = PaymentLog(amount=amount, invoice=invoice)
    payment_log.save()


@csrf_exempt
def webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseForbidden("Need to use request method POST")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body
    if not "HTTP_STRIPE_SIGNATURE" in request.META:
        logging.error(f"No HTTP_STRIPE_SIGNATURE in request.META = {request.META}")
        return HttpResponse(status=400)
    sig_header: str = request.META["HTTP_STRIPE_SIGNATURE"]
    # logging.debug(payload)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # Invalid payload
        logging.error("Invalid payload for " + str(e))
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:  # type: ignore
        # Invalid signature
        logging.error("Invalid signature for " + str(e))
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event
    logging.debug(event)
    if event["type"] == "checkout.session.completed":
        process_payment(
            amount=int(event["data"]["object"]["amount_total"] / 100),
            invoice=get_object_or_404(
                Invoice, pk=int(event["data"]["object"]["client_reference_id"])
            ),
        )
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


class WorkerUpdate(LoginRequiredMixin, UpdateView[Worker, BaseModelForm[Worker]]):
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


class JobFolderList(LoginRequiredMixin, ListView[JobFolder]):
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
            .order_by("name")
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        assert isinstance(self.request.user, User)
        try:
            context["worker"] = Worker.objects.get(user=self.request.user)
        except Worker.DoesNotExist:
            context["worker"] = None
        return context


class JobList(LoginRequiredMixin, ListView[Job]):
    model = Job
    context_object_name = "jobs"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any):
        super().setup(request, *args, **kwargs)
        self.jobfolder = get_object_or_404(JobFolder, slug=self.kwargs["slug"])

    def get_queryset(self) -> QuerySet[Job]:
        return (
            Job.objects.filter(folder=self.jobfolder)
            .annotate(assignee_count=Count("assignee"))
            .order_by(
                "assignee_count",
                "progress",
                "-updated_at",
            )
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["jobfolder"] = self.jobfolder
        return context


class JobDetail(LoginRequiredMixin, DetailView[Job]):
    model = Job
    context_object_name = "job"


@login_required
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
            try:
                job.semester = Semester.objects.get(active=True)
            except Semester.DoesNotExist:
                pass
            job.save()
            messages.success(
                request, f"You have successfully claimed task #{ job.pk }."
            )
        return HttpResponseRedirect(job.get_absolute_url())


class JobUpdate(LoginRequiredMixin, UpdateView[Job, BaseModelForm[Job]]):
    model = Job
    context_object_name = "job"
    template_name = "payments/job_form.html"
    fields = (
        "payment_preference",
        "hours_estimate",
        "worker_deliverable",
        "worker_notes",
    )

    def post(self, *args: Any, **kwargs: Any):
        response = super().post(*args, **kwargs)
        job = self.object
        if job.assignee is None:
            raise PermissionDenied("Someone needs to claim this job first.")
        elif self.request.user != job.assignee.user:
            raise PermissionDenied("Can't submit for someone else's claim.")
        elif job.status == "JOB_VFD":
            raise PermissionDenied("This job is already completed.")
        return response

    def form_valid(self, form: BaseModelForm[Job]):
        self.object.progress = "JOB_SUB"
        messages.success(self.request, "Successfully submitted.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()
