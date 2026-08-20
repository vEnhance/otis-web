import datetime
from typing import Any

import pytest
import stripe
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.aggregates import Sum
from django.db.utils import IntegrityError
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from payments.factories import (
    JobFactory,
    JobFolderFactory,
    PaymentLogFactory,
    WorkerFactory,
)
from payments.models import Job, PaymentLog, Worker
from payments.views import InactiveWorkerList
from roster.factories import InvoiceFactory, StudentFactory

from .views import process_payment, process_reversal

UTC = datetime.UTC


@pytest.fixture
def payment_test_data(db):
    verified_group = GroupFactory(name="Verified")
    alice = StudentFactory.create(
        user__username="alice",
        user__groups=(verified_group,),
    )
    invoice = InvoiceFactory.create(student=alice)
    checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
    return {
        "alice": alice,
        "invoice": invoice,
        "checksum": checksum,
    }


@pytest.mark.django_db
def test_invoice_standalone(otis, payment_test_data):
    alice = payment_test_data["alice"]
    invoice = payment_test_data["invoice"]
    checksum = payment_test_data["checksum"]

    otis.get_denied("payments-invoice", alice.pk, "?")
    otis.login(alice)
    otis.get_denied("payments-invoice", alice.pk, "?")
    str(invoice)  # make sure __str__ is alive
    otis.get_20x("payments-invoice", alice.pk, checksum)

    bob = StudentFactory.create(user__username="bob")
    otis.get_not_found(
        "payments-invoice", bob.pk, bob.get_checksum(settings.INVOICE_HASH_KEY)
    )


@pytest.mark.django_db
def test_config(otis):
    otis.post_40x("payments-config")
    resp = otis.get_20x("payments-config")
    assert "publicKey" in resp.json()


@pytest.mark.django_db
def test_checkout(otis, payment_test_data):
    invoice = payment_test_data["invoice"]
    checksum = payment_test_data["checksum"]
    pk = invoice.pk
    otis.post_40x("payments-checkout", pk, 240, checksum)
    otis.get_40x("payments-checkout", pk, 0, checksum)  # amount >= 0
    otis.get_denied("payments-checkout", pk, 240, "?")  # bad checksum
    otis.get_not_found("payments-checkout", pk + 1, 240, checksum)  # no such invoice

    # the checksum of some other student shouldn't work either
    bob = StudentFactory.create(user__username="bob")
    otis.get_denied(
        "payments-checkout",
        pk,
        240,
        bob.get_checksum(settings.INVOICE_HASH_KEY),
    )

    if settings.STRIPE_PUBLISHABLE_KEY:
        resp = otis.get_20x("payments-checkout", pk, 480, checksum)
        assert "sessionId" in resp.json()


@pytest.mark.django_db
def test_process_payment(payment_test_data):
    invoice = payment_test_data["invoice"]
    process_payment(300, invoice, "pm_XXXXXXXX")
    assert invoice.total_owed == 180
    log = PaymentLog.objects.get()
    assert log.invoice_id == invoice.pk
    assert log.amount == 300


@pytest.mark.django_db
def test_process_payment_is_idempotent(payment_test_data):
    invoice = payment_test_data["invoice"]

    # Stripe retries a delivery it didn't get an answer to; the second one
    # must not credit the invoice again
    first = process_payment(300, invoice, "pm_XXXXXXXX")
    again = process_payment(300, invoice, "pm_XXXXXXXX")

    assert again.pk == first.pk
    assert PaymentLog.objects.count() == 1
    invoice.refresh_from_db()
    assert invoice.total_paid == 300

    # a genuinely different payment still goes through
    process_payment(120, invoice, "pm_YYYYYYYY")
    invoice.refresh_from_db()
    assert invoice.total_paid == 420

    # ...as do payments recorded by hand, which carry no payment intent
    process_payment(50, invoice)
    process_payment(50, invoice)
    invoice.refresh_from_db()
    assert invoice.total_paid == 520


@pytest.mark.django_db
def test_payment_intent_is_unique_in_database(payment_test_data):
    """The database is the backstop if two duplicate deliveries race each other."""
    invoice = payment_test_data["invoice"]
    PaymentLogFactory.create(invoice=invoice, amount=300, stripe_id="pm_XXXXXXXX")

    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentLogFactory.create(invoice=invoice, amount=300, stripe_id="pm_XXXXXXXX")

    # a refund shares the payment intent of the payment it reverses, though
    PaymentLogFactory.create(invoice=invoice, amount=-300, stripe_id="pm_XXXXXXXX")
    # and payments entered by hand have no payment intent to collide over
    PaymentLogFactory.create_batch(2, invoice=invoice, amount=300)


@pytest.mark.django_db
def test_process_reversal(payment_test_data):
    invoice = payment_test_data["invoice"]
    process_payment(300, invoice, "pm_XXXXXXXX")

    # a refund of half the payment takes back half the credit
    process_reversal("pm_XXXXXXXX", 15000)
    invoice.refresh_from_db()
    assert invoice.total_paid == 150
    assert PaymentLog.objects.get(amount=-150).invoice_id == invoice.pk
    assert not PaymentLog.objects.filter(refunded=True).exists()

    # Stripe reports the running total refunded, so redelivering that event
    # (or the matching dispute event) changes nothing
    assert process_reversal("pm_XXXXXXXX", 15000) is None
    invoice.refresh_from_db()
    assert invoice.total_paid == 150

    # refunding the rest takes back the rest, and only the rest
    process_reversal("pm_XXXXXXXX", 30000)
    invoice.refresh_from_db()
    assert invoice.total_paid == 0
    assert PaymentLog.objects.filter(refunded=False).count() == 0

    # a reversal larger than the payment can't drive the invoice negative
    assert process_reversal("pm_XXXXXXXX", 99999) is None
    invoice.refresh_from_db()
    assert invoice.total_paid == 0

    # and re-delivering the original payment event doesn't restore the credit
    process_payment(300, invoice, "pm_XXXXXXXX")
    invoice.refresh_from_db()
    assert invoice.total_paid == 0


@pytest.mark.django_db
def test_process_reversal_of_unknown_payment(payment_test_data):
    invoice = payment_test_data["invoice"]
    assert process_reversal("pm_NOSUCHPAYMENT", 30000) is None
    invoice.refresh_from_db()
    assert invoice.total_paid == 0
    assert not PaymentLog.objects.exists()


@pytest.mark.django_db
def test_payment_log_total_matches_invoice(payment_test_data):
    """The aincrad sync recomputes total_paid by summing the un-refunded logs.

    That sum has to agree with what the webhook credited, both after a partial
    refund (where the negative log cancels part of the payment) and after a full
    one (where every row involved is skipped instead).
    """
    invoice = payment_test_data["invoice"]

    def logged_total() -> int:
        logs = PaymentLog.objects.filter(invoice=invoice, refunded=False)
        return logs.aggregate(s=Sum("amount"))["s"] or 0

    process_payment(300, invoice, "pm_XXXXXXXX")
    process_payment(120, invoice, "pm_YYYYYYYY")
    invoice.refresh_from_db()
    assert logged_total() == invoice.total_paid == 420

    process_reversal("pm_XXXXXXXX", 10000)
    invoice.refresh_from_db()
    assert logged_total() == invoice.total_paid == 320

    process_reversal("pm_XXXXXXXX", 30000)
    invoice.refresh_from_db()
    assert logged_total() == invoice.total_paid == 120


@pytest.mark.django_db
def test_webhook(otis):
    otis.get_40x("payments-webhook")
    otis.post_40x("payments-webhook")
    otis.post_40x("payments-webhook", HTTP_STRIPE_SIGNATURE="meow")


@pytest.mark.django_db
def test_webhook_events(otis, monkeypatch, payment_test_data):
    invoice = payment_test_data["invoice"]
    event: dict[str, Any] = {}

    def fake_construct_event(payload: bytes, sig_header: str, secret: str):
        del payload, sig_header, secret
        return event

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)

    def deliver(event_type: str, **obj: Any) -> None:
        nonlocal event
        event = {"type": event_type, "data": {"object": obj}}
        otis.post_20x("payments-webhook", HTTP_STRIPE_SIGNATURE="meow")

    deliver(
        "checkout.session.completed",
        amount_total=30000,
        client_reference_id=str(invoice.pk),
        payment_intent="pm_XXXXXXXX",
    )
    invoice.refresh_from_db()
    assert invoice.total_paid == 300

    # a duplicate delivery of the same event is acknowledged but not credited
    deliver(
        "checkout.session.completed",
        amount_total=30000,
        client_reference_id=str(invoice.pk),
        payment_intent="pm_XXXXXXXX",
    )
    invoice.refresh_from_db()
    assert invoice.total_paid == 300
    assert PaymentLog.objects.count() == 1

    # a chargeback pulls the money back out...
    deliver("charge.dispute.created", amount=30000, payment_intent="pm_XXXXXXXX")
    invoice.refresh_from_db()
    assert invoice.total_paid == 0
    assert PaymentLog.objects.filter(refunded=False).count() == 0

    # ...and the follow-up event for the same dispute doesn't double count
    deliver(
        "charge.dispute.funds_withdrawn", amount=30000, payment_intent="pm_XXXXXXXX"
    )
    invoice.refresh_from_db()
    assert invoice.total_paid == 0
    assert PaymentLog.objects.count() == 2

    # events we don't act on are still acknowledged
    deliver("payment_intent.created", amount=30000, payment_intent="pm_XXXXXXXX")
    invoice.refresh_from_db()
    assert invoice.total_paid == 0
    assert PaymentLog.objects.count() == 2


@pytest.mark.django_db
def test_webhook_refund_without_payment_intent(otis, monkeypatch, payment_test_data):
    """Stripe should always name the payment intent, but a refund that somehow
    arrives without one must not blow up the endpoint."""
    invoice = payment_test_data["invoice"]
    process_payment(300, invoice, "pm_XXXXXXXX")

    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda payload, sig_header, secret: {
            "type": "charge.refunded",
            "data": {"object": {"amount_refunded": 30000}},
        },
    )
    otis.post_20x("payments-webhook", HTTP_STRIPE_SIGNATURE="meow")
    invoice.refresh_from_db()
    assert invoice.total_paid == 300


@pytest.mark.django_db
def test_success(otis):
    otis.get_20x("payments-success")


@pytest.mark.django_db
def test_cancelled(otis):
    otis.get_20x("payments-cancelled")


@pytest.mark.django_db
def test_worker(otis) -> None:
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)

    resp = otis.post_ok(
        "worker-update",
        data={"gmail_address": "alice.aardvark@gmail.com", "notes": "hi there"},
        follow=True,
    )
    worker = Worker.objects.get(user__username="alice")
    assert worker.gmail_address == "alice.aardvark@gmail.com"
    assert worker.notes == "hi there"

    resp = otis.post_ok(
        "worker-update",
        data={
            "gmail_address": "alice.aardvark@gmail.com",
            "venmo_handle": "@Alice-Aardvark-42",
            "notes": "hello again",
        },
        follow=True,
    )
    worker = Worker.objects.get(user__username="alice")
    assert worker.gmail_address == "alice.aardvark@gmail.com"
    assert worker.venmo_handle == "@Alice-Aardvark-42"
    assert worker.notes == "hello again"

    resp = otis.post_ok(
        "worker-update",
        data={
            "venmo_handle": "AARDVARK",
            "notes": "this should fail due to validation errors",
        },
        follow=True,
    )
    assert resp.context["form"].errors
    worker = Worker.objects.get(user__username="alice")
    assert worker.gmail_address == "alice.aardvark@gmail.com"
    assert worker.venmo_handle == "@Alice-Aardvark-42"
    assert worker.notes == "hello again"

    resp = otis.post_ok(
        "worker-update",
        data={
            "gmail_address": "alice.aardvark",
            "notes": "this should fail due to validation errors",
        },
        follow=True,
    )
    assert resp.context["form"].errors
    worker = Worker.objects.get(user__username="alice")
    assert worker.gmail_address == "alice.aardvark@gmail.com"
    assert worker.venmo_handle == "@Alice-Aardvark-42"
    assert worker.notes == "hello again"


@pytest.mark.django_db
def test_claim_limits(otis) -> None:
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)
    otis.post_ok("worker-update", data={"notes": "hi"}, follow=True)
    worker = Worker.objects.get(user=alice)

    folder = JobFolderFactory.create(max_pending=3, max_total=5)
    jobs = JobFactory.create_batch(10, folder=folder)

    for i in range(3):
        otis.post_ok("job-claim", jobs[i].pk, follow=True)
        jobs[i].refresh_from_db()
        assert jobs[i].assignee == worker
    for i in range(3):
        otis.assert_message(
            otis.post_ok("job-claim", jobs[i].pk, follow=True),
            "This task is already claimed.",
        )

    otis.assert_message(
        otis.post_ok("job-claim", jobs[3].pk, follow=True),
        "You already reached the maximum number of pending tasks for this category.",
    )

    for i in range(3):
        Job.objects.filter(pk__in=[jobs[i].pk for i in range(3)]).update(
            progress="JOB_VFD"
        )

    for i in range(3, 5):
        otis.post_ok("job-claim", jobs[i].pk, follow=True)
        jobs[i].refresh_from_db()
        assert jobs[i].assignee == worker
    otis.assert_message(
        otis.post_ok("job-claim", jobs[5].pk, follow=True),
        "You already reached the maximum number of total tasks for this category.",
    )


@pytest.mark.django_db
def test_claim_rejects_get(otis) -> None:
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)
    otis.post_ok("worker-update", data={"notes": "hi"}, follow=True)
    job = JobFactory.create()

    # a cross-site navigation is a GET, so claiming can't be reachable that way
    assert otis.get("job-claim", job.pk).status_code == 405
    job.refresh_from_db()
    assert job.assignee is None


@pytest.mark.django_db
def test_job_update_permissions(otis) -> None:
    verified_group = GroupFactory(name="Verified")
    alice = WorkerFactory.create(user__username="alice", user__groups=(verified_group,))
    bob = WorkerFactory.create(user__username="bob", user__groups=(verified_group,))
    admin: User = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    folder = JobFolderFactory.create()
    unclaimed = JobFactory.create(folder=folder)
    alices_job = JobFactory.create(
        folder=folder,
        assignee=alice,
        worker_deliverable="alice-secret-deliverable",
        worker_notes="alice-secret-notes",
    )
    done_job = JobFactory.create(folder=folder, assignee=alice, progress="JOB_VFD")

    payload = {"payment_preference": "PREF_PROBONO", "worker_deliverable": "stolen"}

    def assert_unchanged(job: Job) -> None:
        job.refresh_from_db()
        assert job.worker_deliverable == "alice-secret-deliverable"
        assert job.worker_notes == "alice-secret-notes"
        assert job.progress == "JOB_NEW"

    # anonymous users get bounced to the login page
    otis.get_30x("job-update", alices_job.pk)
    otis.post_30x("job-update", alices_job.pk, data=payload)
    assert_unchanged(alices_job)

    # a verified user who isn't the assignee must not see or touch the submission
    otis.login(bob.user)
    otis.assert_not_has(
        otis.get_denied("job-update", alices_job.pk), "alice-secret-deliverable"
    )
    otis.post_denied("job-update", alices_job.pk, data=payload)
    assert_unchanged(alices_job)

    # ...and neither may staff, who go through the admin instead
    otis.login(admin)
    otis.assert_not_has(
        otis.get_denied("job-update", alices_job.pk), "alice-secret-deliverable"
    )
    otis.post_denied("job-update", alices_job.pk, data=payload)
    assert_unchanged(alices_job)

    otis.login(alice.user)
    # an unclaimed job can't be submitted, even by a worker in good standing
    otis.get_denied("job-update", unclaimed.pk)
    otis.post_denied("job-update", unclaimed.pk, data=payload)
    unclaimed.refresh_from_db()
    assert unclaimed.worker_deliverable == ""

    # nor can a job that's already been signed off on
    otis.get_denied("job-update", done_job.pk)
    otis.post_denied("job-update", done_job.pk, data=payload)
    done_job.refresh_from_db()
    assert done_job.worker_deliverable == ""

    # but the assignee can see her own form and submit it
    otis.assert_has(
        otis.get_20x("job-update", alices_job.pk), "alice-secret-deliverable"
    )
    otis.post_30x(
        "job-update",
        alices_job.pk,
        data={
            "payment_preference": "PREF_VENMO",
            "worker_deliverable": "here is my work",
            "worker_notes": "took a while",
        },
    )
    alices_job.refresh_from_db()
    assert alices_job.worker_deliverable == "here is my work"
    assert alices_job.worker_notes == "took a while"
    assert alices_job.payment_preference == "PREF_VENMO"
    assert alices_job.progress == "JOB_SUB"

    # having submitted, she still can't reach someone else's job
    bobs_job = JobFactory.create(folder=folder, assignee=bob)
    otis.get_denied("job-update", bobs_job.pk)
    otis.post_denied("job-update", bobs_job.pk, data=payload)
    bobs_job.refresh_from_db()
    assert bobs_job.worker_deliverable == ""


@pytest.mark.django_db
def test_inactive_worker_list(otis) -> None:
    folder = JobFolderFactory.create(slug="art")

    alice = WorkerFactory.create(
        user__first_name="Alice",
        user__last_name="Aardvark",
        user__email="alice@example.com",
    )
    bob = WorkerFactory.create(
        user__first_name="Bob",
        user__last_name="Beta",
        user__email="bob@example.com",
    )
    carol = WorkerFactory.create(
        user__first_name="Carol",
        user__last_name="Cutie",
        user__email="carol@example.com",
    )

    to_pass_as_kwargs = [
        {"assignee": alice, "progress": "JOB_VFD"},  # Jan 1
        {"assignee": alice, "progress": "JOB_REV"},  # Jan 2
        {"assignee": alice, "progress": "JOB_NEW"},  # Jan 3
        {"assignee": alice, "progress": "JOB_NEW"},  # Jan 4
        {"assignee": bob, "progress": "JOB_NEW"},  # Jan 5
        {"assignee": bob, "progress": "JOB_NEW"},  # Jan 6
        {"assignee": carol, "progress": "JOB_VFD"},  # Jan 7
        {"assignee": carol, "progress": "JOB_VFD"},  # Jan 8
    ]
    for i, kwargs in enumerate(to_pass_as_kwargs):
        with freeze_time(f"2023-01-{i + 1:02d}", tz_offset=0):
            JobFactory.create(folder=folder, **kwargs)

    # first make sure staff protection works
    otis.get_30x("job-inactive", "art")  # redirect anonymous
    otis.login(alice.user)
    otis.get_40x("job-inactive", "art")

    # now actually log in and load the details
    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)
    resp = otis.get_20x("job-inactive", "art")
    assert {w.user.get_full_name() for w in resp.context["workers"]} == {
        "Alice Aardvark",
        "Bob Beta",
    }

    view = otis.setup_view_get(InactiveWorkerList, "job-inactive", "art")
    assert isinstance(view, InactiveWorkerList)
    queryset = view.get_queryset()
    assert queryset.count() == 2

    a = queryset.get(user=alice.user)
    assert a.latest_update.day == 4  # type: ignore
    assert a.oldest_undone.day == 2  # type: ignore
    assert a.num_completed == 1  # type: ignore
    assert a.num_total == 4  # type: ignore

    b = queryset.get(user=bob.user)
    assert b.latest_update.day == 6  # type: ignore
    assert b.oldest_undone.day == 5  # type: ignore
    assert b.num_completed == 0  # type: ignore
    assert b.num_total == 2  # type: ignore
