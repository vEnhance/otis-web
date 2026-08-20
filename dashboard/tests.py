import datetime
import os
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.messages import constants as message_levels
from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse
from freezegun import freeze_time

from core.factories import (
    GroupFactory,
    SemesterFactory,
    UnitFactory,
    UnitGroupFactory,
    UserFactory,
    UserProfileFactory,
)
from core.models import Unit
from dashboard.admin import AnnouncementAdmin
from dashboard.factories import (
    AnnouncementFactory,
    PSetFactory,
    SemesterDownloadFileFactory,
)
from dashboard.models import Announcement, PSet
from dashboard.utils import get_news, get_units_to_submit, get_units_to_unlock
from exams.factories import PracticeExamFactory, QuizFactory
from hanabi.factories import HanabiContestFactory
from markets.factories import MarketFactory
from opal.factories import OpalHuntFactory
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
)
from rpg.factories import BonusLevelFactory
from rpg.models import Level

UTC = datetime.UTC


@pytest.mark.django_db
def test_portal_invoice_redirect(otis):
    semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
    )
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=alice)

    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_redirects(
            reverse("invoice", args=(alice.pk,)), "portal", alice.pk, follow=True
        )


@pytest.mark.django_db
def test_portal(otis):
    semester = SemesterFactory.create(exam_family="Waltz")
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    # A bunch of context things to check

    unit = UnitFactory.create(code="BMX")
    alice.curriculum.set([unit])
    alice.unlocked_units.add(unit)

    PSetFactory.create(student=alice, clubs=501, hours=0, status="A", unit=unit)

    alice_profile = UserProfileFactory.create(user=alice.user)
    alice_profile.last_notif_dismiss = datetime.datetime(2021, 6, 1, tzinfo=UTC)
    alice_profile.save()

    prevSemester = SemesterFactory.create(end_year=2020)
    StudentFactory.create(user=alice.user, semester=prevSemester)

    test = PracticeExamFactory.create(
        start_date=datetime.datetime(2021, 6, 1, tzinfo=UTC),
        due_date=datetime.datetime(2021, 7, 31, tzinfo=UTC),
        family="Waltz",
        number=1,
    )

    quiz = QuizFactory.create(
        start_date=datetime.datetime(2021, 6, 1, tzinfo=UTC),
        due_date=datetime.datetime(2021, 7, 31, tzinfo=UTC),
        family="Waltz",
        number=1,
    )

    # an assistant viewing the portal must not consume the student's level-up
    assistant = AssistantFactory.create()
    alice.assistant = assistant
    alice.save()
    otis.login(assistant)
    with freeze_time("2021-07-01", tz_offset=0):
        resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["level_number"] == 22
    alice.refresh_from_db()
    assert alice.last_level_seen != 22
    assert not resp.context["messages"]

    # but the student seeing it themselves does level up, and is told
    otis.login(alice)
    with freeze_time("2021-07-01", tz_offset=0):
        resp = otis.get_20x("portal", alice.pk, follow=True)

    assert resp.context["level_number"] == 22
    alice.refresh_from_db()
    assert alice.last_level_seen == 22
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])

    # static stuff
    assert resp.context["title"] == f"{alice.name} ({alice.semester.name})"
    assert resp.context["meters"]["clubs"].value == 501
    assert 2020 in [row["semester__end_year"] for row in resp.context["history"]]
    assert [row["unit"] for row in resp.context["curriculum"]] == [unit]
    assert list(resp.context["tests"]) == [test]
    assert list(resp.context["quizzes"]) == [quiz]


@pytest.mark.django_db
def test_get_news(otis):
    semester = SemesterFactory.create(exam_family="Waltz")
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    # A bunch of context things to check
    alice_profile = UserProfileFactory.create(
        user=alice.user,
        last_notif_dismiss=datetime.datetime(2021, 6, 1, tzinfo=UTC),
    )

    # News items
    for y in (2020, 2020, 2020, 2021, 2022, 2022):
        MarketFactory.create(
            start_date=datetime.datetime(y, 6, 30, tzinfo=UTC),
            end_date=datetime.datetime(y, 7, 20, tzinfo=UTC),
        )
        HanabiContestFactory.create(
            start_date=datetime.datetime(y, 6, 30, tzinfo=UTC),
            end_date=datetime.datetime(y, 7, 25, tzinfo=UTC),
        )
        OpalHuntFactory.create(
            start_date=datetime.datetime(2021, 6, 30, tzinfo=UTC),
            active=(y == 2021),
        )

    with freeze_time("2021-06-30", tz_offset=0):
        AnnouncementFactory.create()

    with freeze_time("2021-07-01", tz_offset=0):
        SemesterDownloadFileFactory.create(semester=semester)

    with freeze_time("2021-07-01", tz_offset=0):
        news = get_news(alice_profile, alice)
        assert news["announcements"].count() == 1
        assert news["downloads"].count() == 1
        assert news["markets"].count() == 1
        assert news["hanabis"].count() == 1
        assert news["opals"].count() == 1

    with freeze_time("2021-07-30", tz_offset=0):
        news = get_news(alice_profile, alice)
        assert not news["announcements"].exists()
        assert not news["downloads"].exists()
        assert not news["markets"].exists()
        assert not news["hanabis"].exists()
        assert news["opals"].count() == 1

    # alice dismisses stuff
    alice_profile.last_notif_dismiss = datetime.datetime(2021, 7, 2, tzinfo=UTC)
    alice_profile.save()

    with freeze_time("2021-07-02", tz_offset=0):
        news = get_news(alice_profile, alice)
        assert not news["announcements"].exists()
        assert not news["downloads"].exists()
        assert not news["markets"].exists()
        assert not news["hanabis"].exists()
        assert not news["opals"].exists()

    with freeze_time("2022-07-02", tz_offset=0):
        SemesterDownloadFileFactory.create(semester=semester)
        news = get_news(alice_profile, alice)
        assert not news["announcements"].exists()
        assert news["downloads"].count() == 1
        assert news["markets"].count() == 2
        assert news["hanabis"].count() == 2
        assert not news["opals"].exists()


@pytest.mark.django_db
def test_announcements(otis):
    AnnouncementFactory.create(slug="one", content="하나")
    AnnouncementFactory.create(slug="two", content="둘")
    AnnouncementFactory.create(slug="three", content="셋")

    # First make sure nothing is accessible to outside world
    mallory = UserFactory.create(username="mallory")
    otis.login(mallory)
    otis.get_40x("announcement-list")
    otis.get_40x("announcement-detail", "one")
    otis.get_40x("announcement-detail", "two")
    otis.get_40x("announcement-detail", "three")

    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)
    otis.assert_has(otis.get_20x("announcement-list"), "one")
    otis.assert_has(otis.get_20x("announcement-detail", "one"), "하나")
    otis.assert_has(otis.get_20x("announcement-detail", "two"), "둘")
    otis.assert_has(otis.get_20x("announcement-detail", "three"), "셋")


@pytest.mark.django_db
def test_announcement_archive(otis):
    current = AnnouncementFactory.create(slug="current", subject="Fresh news")
    stale = AnnouncementFactory.create(slug="stale", subject="Ancient news")

    verified_group = GroupFactory(name="Verified")
    otis.login(UserFactory.create(username="alice", groups=(verified_group,)))

    # by default nothing is archived, so the past years section is hidden
    response = otis.get_20x("announcement-list")
    assert set(response.context["current_announcements"]) == {stale, current}
    assert list(response.context["archived_announcements"]) == []

    # the admin action archives in bulk
    admin = AnnouncementAdmin(Announcement, AdminSite())
    request: HttpRequest = RequestFactory().get("/")
    request._messages = CookieStorage(request)
    admin.archive_announcements(request, Announcement.objects.filter(slug="stale"))

    stale.refresh_from_db()
    current.refresh_from_db()
    assert stale.archived is True
    assert current.archived is False

    response = otis.get_20x("announcement-list")
    assert list(response.context["current_announcements"]) == [current]
    assert list(response.context["archived_announcements"]) == [stale]

    # ... and unarchives them again
    admin.unarchive_announcements(request, Announcement.objects.filter(slug="stale"))
    stale.refresh_from_db()
    assert stale.archived is False


@pytest.mark.django_db
def test_certify(otis):
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    unit = UnitFactory.create(code="BMX")
    alice.curriculum.set([unit])
    alice.unlocked_units.add(unit)

    PSetFactory.create(student=alice, clubs=0, hours=1501, status="A", unit=unit)
    Level.objects.create(name="Level Thirty Eight", threshold=38)

    checksum = alice.get_checksum(settings.CERT_HASH_KEY)

    resp = otis.get_20x(
        "certify",
        alice.pk,
        checksum,
        follow=True,
    )

    assert resp.context["hearts"] == 1501
    assert resp.context["level_number"] == 38
    assert resp.context["level_name"] == "Level Thirty Eight"

    otis.get_denied("certify", alice.pk, "invalid")
    otis.get_20x("certify", alice.pk, checksum)

    eve = StudentFactory.create(semester=semester)
    otis.login(eve)
    otis.get_denied("certify", alice.pk)


@pytest.mark.django_db
def test_submit_permissions(otis):
    # delinquent

    semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
    )
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=alice)

    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("submit-pset", alice.pk)

    # unenabled
    bob = StudentFactory.create(enabled=False)
    otis.login(bob)

    otis.get_denied("submit-pset", bob.pk)

    # inactive semester
    carl = StudentFactory.create(semester=SemesterFactory.create(active=False))
    otis.login(carl)

    otis.get_denied("submit-pset", carl.pk)


@pytest.mark.django_db
def test_submit(otis):
    unit1 = UnitFactory.create(code="BMW")
    unit2 = UnitFactory.create(code="DMX")
    unit3 = UnitFactory.create(code="ZMY")
    alice = StudentFactory.create()
    otis.login(alice)
    alice.unlocked_units.add(unit1)
    alice.curriculum.set([unit1, unit2, unit3])

    # Alice should show initially as Level 0
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 0

    # Alice submits a problem set
    resp = otis.get_20x("submit-pset", alice.pk)
    assert resp.context["title"] == "Ready to submit?"

    content1 = StringIO("Meow")
    content1.name = "content1.txt"
    resp = otis.post_20x(
        "submit-pset",
        alice.pk,
        data={
            "unit": unit1.pk,
            "clubs": 13,
            "hours": 37,
            "feedback": "hello",
            "special_notes": "meow",
            "content": content1,
            "next_unit_to_unlock": unit2.pk,
        },
        follow=True,
    )
    otis.assert_testid(resp, "pset-status-pending")
    assert resp.context["pset"].clubs == 13
    assert resp.context["pset"].hours == 37

    # Alice should still be Level 0 though
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 0

    # Check pset reflects this data
    pset = PSet.objects.get(student=alice, unit=unit1)
    assert pset.clubs == 13
    assert pset.hours == 37
    assert pset.feedback == "hello"
    assert pset.special_notes == "meow"
    assert os.path.basename(pset.upload.content.name) == "content1.txt"
    assert not pset.accepted
    assert not pset.resubmitted

    # Alice realizes she made a typo in hours and edits the problem set
    resp = otis.get_20x("resubmit-pset", alice.pk)
    assert resp.context["pset"].filename == "content1.txt"

    content2 = StringIO("Purr")
    content2.name = "content2.txt"
    resp = otis.post_20x(
        "resubmit-pset",
        alice.pk,
        data={
            "unit": unit1.pk,
            "clubs": 13,
            "hours": 3.7,
            "feedback": "hello",
            "special_notes": "meow",
            "content": content2,
            "next_unit_to_unlock": unit3.pk,
        },
        follow=True,
    )
    otis.assert_testid(resp, "pset-status-pending")
    assert resp.context["pset"].clubs == 13
    assert resp.context["pset"].hours == 3.7

    # Check the updated problem set object
    pset = PSet.objects.get(student=alice, unit=unit1)
    assert pset.clubs == 13
    assert pset.hours == 3.7
    assert pset.feedback == "hello"
    assert pset.special_notes == "meow"
    assert os.path.basename(pset.upload.content.name) == "content2.txt"
    assert not pset.accepted
    assert not pset.resubmitted

    # Alice should still be Level 0 though
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 0

    # update again, but this time change just the metadata
    resp = otis.post_20x(
        "resubmit-pset",
        alice.pk,
        data={
            "unit": unit1.pk,
            "clubs": 13,
            "hours": 3.7,
            "feedback": "good day",
            "special_notes": "purr",
            "next_unit_to_unlock": unit3.pk,
        },
        follow=True,
    )
    otis.assert_testid(resp, "pset-status-pending")
    assert resp.context["pset"].clubs == 13
    assert resp.context["pset"].hours == 3.7

    # Check the updated problem set object
    pset = PSet.objects.get(student=alice, unit=unit1)
    assert pset.clubs == 13
    assert pset.hours == 3.7
    assert pset.feedback == "good day"
    assert pset.special_notes == "purr"
    assert os.path.basename(pset.upload.content.name) == "content2.txt"
    assert not pset.accepted
    assert not pset.resubmitted

    # simulate acceptance
    pset.status = "A"
    pset.save()
    alice.unlocked_units.remove(unit1)
    alice.unlocked_units.add(unit2)
    alice.curriculum.set([unit1, unit2, unit3])

    # check it shows up this way
    resp = otis.get_20x("pset", pset.pk)
    otis.assert_testid(resp, "pset-status-accepted")
    assert resp.context["pset"].clubs == 13
    assert resp.context["pset"].hours == 3.7

    # Alice should show as leveled up now
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 4

    # now let's say Alice resubmits
    content3 = StringIO("Rawr")
    content3.name = "content3.txt"
    resp = otis.post_20x(
        "resubmit-pset",
        alice.pk,
        data={
            "unit": unit1.pk,
            "clubs": 100,
            "hours": 20,
            "feedback": "hello",
            "special_notes": "meow",
            "content": content3,
            "next_unit_to_unlock": unit2.pk,
        },
        follow=True,
    )

    # check it shows up this way
    resp = otis.get_20x("pset", pset.pk)
    otis.assert_testid(resp, "pset-status-pending")
    assert resp.context["pset"].clubs == 100
    assert resp.context["pset"].hours == 20

    # Check the problem set
    pset = PSet.objects.get(student=alice, unit=unit1)
    assert pset.clubs == 100
    assert pset.hours == 20
    assert pset.feedback == "hello"
    assert pset.special_notes == "meow"
    assert os.path.basename(pset.upload.content.name) == "content3.txt"
    assert not pset.accepted
    assert pset.resubmitted

    # Alice is now back to Level 0
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 0

    # simulate acceptance
    pset.status = "A"
    pset.save()

    # Alice is now Level 14
    resp = otis.get_20x("stats", alice.pk)
    assert resp.context["level_number"] == 14

    # check it shows up this way
    resp = otis.get_20x("pset", pset.pk)
    otis.assert_testid(resp, "pset-status-accepted")
    assert resp.context["pset"].clubs == 100
    assert resp.context["pset"].hours == 20


@pytest.mark.django_db
def test_unit_query(otis):
    units = UnitFactory.create_batch(size=20)
    alice = StudentFactory.create()
    alice.curriculum.set(units[:18])
    alice.unlocked_units.set(units[4:7])
    for unit in units[:4]:
        PSetFactory.create(student=alice, unit=unit)
    PSetFactory.create(student=alice, unit=units[4], status="P")

    assert get_units_to_submit(alice).count() == 2
    assert get_units_to_unlock(alice).count() == 11


@pytest.mark.django_db
def test_pset_list(otis):
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    eve = StudentFactory.create(semester=semester)

    unit1 = UnitFactory.create(code="BMW")
    unit2 = UnitFactory.create(code="ZMX")
    unit3 = UnitFactory.create(code="DAY")

    pset1 = PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit1)
    pset2 = PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit2)
    PSetFactory.create(student=eve, clubs=0, hours=0, status="A", unit=unit3)

    # eve's problem set must not leak into alice's listing
    resp = otis.get_20x("student-pset-list", alice.pk)
    assert set(resp.context["object_list"]) == {pset1, pset2}


@pytest.mark.django_db
def test_pset_list_permission(otis):
    semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
    )
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=alice)

    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("student-pset-list", alice.pk)

    eve = StudentFactory.create(semester=semester)

    otis.login(eve)

    otis.get_20x("student-pset-list", eve.pk)
    otis.get_denied("student-pset-list", alice.pk)


@pytest.mark.django_db
def test_index(otis):
    user = UserFactory.create()
    otis.login(user)

    # 0 Students
    resp = otis.get_20x("index")

    assert resp.context["rows"] == []
    otis.assert_no_testid(resp, "stulist-empty-staff")

    # But now they are staff!
    user.is_staff = True
    user.save()
    resp = otis.get_20x("index")
    otis.assert_testid(resp, "stulist-empty-staff")
    user.is_staff = False
    user.save()

    semester = SemesterFactory.create()
    RegistrationContainerFactory.create(semester=semester)
    resp = otis.get_20x("index")
    assert resp.context["exists_registration"] is True
    otis.assert_testid(resp, "stulist-empty-register")

    alice = StudentFactory.create(user=user)
    otis.get_redirects(reverse("portal", args=(alice.pk,)), "index", follow=True)

    assistant = AssistantFactory.create()
    alice.assistant = assistant
    alice.save()
    bob = StudentFactory.create(assistant=assistant)

    otis.login(assistant)
    resp = otis.get_20x("index")
    assert {row["student"] for row in resp.context["rows"]} == {alice, bob}


@pytest.mark.django_db
def test_past(otis):
    prevSemester = SemesterFactory.create(active=False)
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    prevAlice = StudentFactory.create(semester=prevSemester, user=alice.user)

    # With no semester pinned the listing spans years, so both of this user's
    # enrollments appear and the Year column is shown to tell them apart.
    # (Asserting on names cannot distinguish them -- they share a user.)
    resp = otis.get_20x("past")
    assert resp.context["past"] is True
    assert resp.context["stulist_show_semester"] is True
    assert {row["student"] for row in resp.context["rows"]} == {alice, prevAlice}

    unit = UnitFactory.create(code="BMX")
    PSetFactory.create(student=prevAlice, clubs=0, hours=1501, status="A", unit=unit)

    # pinning a semester restricts the listing and swaps Year for Level
    resp = otis.get_20x("past", prevSemester.pk)
    assert resp.context["past"] is True
    assert resp.context["semester"] == prevSemester
    assert resp.context["stulist_show_semester"] is False
    (row,) = resp.context["rows"]
    assert row["student"] == prevAlice
    assert row["level"] == 38

    assistant = AssistantFactory.create()
    prevAlice.assistant = assistant
    prevAlice.save()
    bob = StudentFactory.create(assistant=assistant, semester=prevSemester)

    otis.login(assistant)
    resp = otis.get_20x("past", prevSemester.pk)
    assert resp.context["semester"] == prevSemester
    rows = {row["student"]: row for row in resp.context["rows"]}
    assert set(rows) == {prevAlice, bob}
    assert rows[prevAlice]["level"] == 38


@pytest.mark.django_db
def test_semester_list(otis):
    prevSemester = SemesterFactory.create(active=False)
    semester = SemesterFactory.create()

    user = UserFactory.create()
    alice = StudentFactory.create(semester=semester, user=user)
    otis.login(alice)

    # the student-count column is superuser-only
    resp = otis.get_20x("semester-list")
    assert prevSemester in resp.context["object_list"]
    otis.assert_no_testid(resp, "semester-student-count")

    user.is_superuser = True
    user.save()

    resp = otis.get_20x("semester-list")
    assert prevSemester in resp.context["object_list"]
    otis.assert_testid(resp, "semester-student-count")


@pytest.mark.django_db
def test_idle_warn(otis):
    user = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(user)

    unit = UnitFactory.create(code="BMX")

    alice = StudentFactory.create(assistant=AssistantFactory.create(user=user))

    with freeze_time("2021-07-01", tz_offset=0):
        PSetFactory.create(student=alice, clubs=0, hours=1501, status="A", unit=unit)

    with freeze_time("2021-07-29", tz_offset=0):
        resp = otis.get_20x("idlewarn")

    assert resp.context["title"] == "Idle-warn"
    (row,) = resp.context["rows"]
    assert row["student"] == alice
    assert row["level"] == 38
    assert row["days_since_last_pset"] == pytest.approx(28.0)


@pytest.mark.django_db
def test_download_list(otis):
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    download = SemesterDownloadFileFactory.create(semester=semester)

    otis.get_40x("downloads", alice.pk + 1)
    resp = otis.get_20x("downloads", alice.pk)

    assert list(resp.context["object_list"]) == [download]


@pytest.mark.django_db
def test_level_up_and_bonus(otis) -> None:
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    secret4 = UnitGroupFactory.create(name="Level 4", subject="K", hidden=True)
    secret9 = UnitGroupFactory.create(name="Level 9", subject="K", hidden=True)
    secret16 = UnitGroupFactory.create(name="Level 16", subject="K", hidden=True)
    for group in (secret4, secret9, secret16):
        for code in ("BKV", "DKV", "ZKV"):
            UnitFactory.create(code=code, group=group)
    BonusLevelFactory.create(level=4, group=secret4)
    BonusLevelFactory.create(level=9, group=secret9)
    BonusLevelFactory.create(level=16, group=secret16)

    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert not resp.context["bonus_levels"]
    otis.assert_no_testid(resp, "bonus-level-request")

    # the form shouldn't have anything in the queryset right now
    resp = otis.get_20x("bonus-level-request", alice.pk, follow=True)
    assert resp.context["form"].fields["unit"].queryset.count() == 0
    messages = [m.message for m in resp.context["messages"]]
    assert "There are no secret units you can request yet." in messages

    # set Alice's level by adding a unit
    PSetFactory.create(
        student=alice,
        clubs=13,
        hours=37,
        status="A",
        unit__code="BCY",
    )
    resp = otis.get_20x("portal", alice.pk, follow=True)
    assert resp.context["bonus_levels"]
    otis.assert_testid(resp, "bonus-level-request")

    # make sure the level up does its job
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    alice.refresh_from_db()
    assert alice.last_level_seen == 9
    assert alice.curriculum.all().count() == 2
    assert alice.curriculum.all()[0].code == "BKV"
    assert alice.curriculum.all()[1].code == "BKV"

    # now there should be six choices in the form
    resp = otis.get_20x("bonus-level-request", alice.pk, follow=True)
    messages = [m.message for m in resp.context["messages"]]
    assert "There are no secret units you can request yet." not in messages
    queryset = resp.context["form"].fields["unit"].queryset
    assert queryset.count() == 6
    assert set(queryset) == set(
        Unit.objects.filter(group__in=(secret4, secret9))  # type: ignore
    )

    # let's submit one and make sure it works
    desired_unit = Unit.objects.get(group=secret9, code="DKV")
    assert queryset.filter(pk=desired_unit.pk).exists()
    assert not alice.curriculum.filter(pk=desired_unit.pk).exists()
    resp = otis.post_20x(
        "bonus-level-request",
        alice.pk,
        data={"unit": desired_unit.pk},
        follow=True,
    )
    messages = [m.message for m in resp.context["messages"]]
    assert "There are no secret units you can request yet." not in messages
    alice.refresh_from_db()
    assert alice.curriculum.filter(pk=desired_unit.pk).exists()


@pytest.mark.django_db
def test_pset_detail_permissions(otis) -> None:
    alice = StudentFactory.create()
    pset = PSetFactory.create(student=alice, feedback="alice-secret-feedback")

    # anonymous users belong at the login page, not at a 403
    otis.assert_not_has(
        otis.get_login_redirect("pset", pset.pk), "alice-secret-feedback"
    )

    # an unrelated student can't read someone else's submission
    eve = StudentFactory.create()
    otis.login(eve)
    otis.assert_not_has(otis.get_denied("pset", pset.pk), "alice-secret-feedback")

    # a staff member who doesn't teach Alice is no better off
    unrelated_assistant = AssistantFactory.create()
    otis.login(unrelated_assistant.user)
    otis.assert_not_has(otis.get_denied("pset", pset.pk), "alice-secret-feedback")

    # but Alice, and the instructor who actually teaches her, can
    otis.login(alice)
    otis.get_20x("pset", pset.pk)

    alice.assistant = AssistantFactory.create()
    alice.save()
    otis.login(alice.assistant.user)
    otis.get_20x("pset", pset.pk)
