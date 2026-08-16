import datetime

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from payments.factories import JobFactory, JobFolderFactory, WorkerFactory
from payments.models import Job, PaymentLog, Worker
from payments.views import InactiveWorkerList
from roster.factories import InvoiceFactory, StudentFactory

from .views import process_payment

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
def test_webhook(otis):
    otis.get_40x("payments-webhook")
    otis.post_40x("payments-webhook")
    otis.post_40x("payments-webhook", HTTP_STRIPE_SIGNATURE="meow")


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
    otis.assert_has(resp, "alice.aardvark@gmail.com")
    otis.assert_has(resp, "hi there")
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
    otis.assert_has(resp, "alice.aardvark")
    otis.assert_has(resp, "hello again")

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
    otis.assert_has(resp, "Enter a valid value.")
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
    otis.assert_has(resp, "Enter a valid value.")
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

    folder = JobFolderFactory.create(max_pending=3, max_total=5)
    jobs = JobFactory.create_batch(10, folder=folder)

    for i in range(3):
        otis.assert_has(
            otis.post_ok("job-claim", jobs[i].pk, follow=True),
            "You have successfully claimed",
        )
    for i in range(3):
        otis.assert_has(
            otis.post_ok("job-claim", jobs[i].pk, follow=True),
            "This task is already claimed",
        )

    otis.assert_has(
        otis.post_ok("job-claim", jobs[3].pk, follow=True),
        "maximum number of pending tasks",
    )

    for i in range(3):
        Job.objects.filter(pk__in=[jobs[i].pk for i in range(3)]).update(
            progress="JOB_VFD"
        )

    for i in range(3, 5):
        otis.assert_has(
            otis.post_ok("job-claim", jobs[i].pk, follow=True),
            "You have successfully claimed",
        )
    otis.assert_has(
        otis.post_ok("job-claim", jobs[5].pk, follow=True),
        "maximum number of total tasks",
    )


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
    otis.assert_has(resp, "Alice Aardvark")
    otis.assert_has(resp, "Bob Beta")
    otis.assert_not_has(resp, "Carol Cutie")

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
