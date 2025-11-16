import datetime
import os
from io import StringIO

import pytest
from django.conf import settings
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
from dashboard.factories import (
    AnnouncementFactory,
    PSetFactory,
    SemesterDownloadFileFactory,
)
from dashboard.models import PSet, UploadedFile
from dashboard.utils import get_news, get_units_to_submit, get_units_to_unlock
from exams.factories import QuizFactory, TestFactory
from hanabi.factories import HanabiContestFactory
from markets.factories import MarketFactory
from opal.factories import OpalHuntFactory
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from rpg.factories import BonusLevelFactory
from rpg.models import Level

UTC = datetime.timezone.utc


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

    test = TestFactory.create(
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

    # assistant does not cause level up message
    assistant = AssistantFactory.create()
    alice.assistant = assistant
    alice.save()
    otis.login(assistant)
    with freeze_time("2021-07-01", tz_offset=0):
        resp = otis.get_20x("portal", alice.pk, follow=True)
    messages = [m.message for m in resp.context["messages"]]
    assert "You leveled up! You're now level 22." not in messages

    otis.login(alice)
    with freeze_time("2021-07-01", tz_offset=0):
        resp = otis.get_20x("portal", alice.pk, follow=True)

    messages = [m.message for m in resp.context["messages"]]
    assert "You leveled up! You're now level 22." in messages

    # static stuff
    otis.assert_has(resp, f"{alice.name} ({alice.semester.name})")
    otis.assert_has(resp, 501)
    otis.assert_has(resp, 2020)
    otis.assert_has(resp, unit.code)
    otis.assert_has(resp, test)
    otis.assert_has(resp, quiz)

    # TODO check for whether meters are being rendered?


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
        assert len(news["markets"]) == 1
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
        assert len(news["downloads"]) == 1
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

    otis.assert_has(resp, 1501)
    otis.assert_has(resp, 38)
    otis.assert_has(resp, "Level Thirty Eight")

    otis.get_denied("certify", alice.pk, "invalid")
    otis.get_20x("certify", alice.pk, checksum)

    eve = StudentFactory.create(semester=semester)
    otis.login(eve)
    otis.get_denied("certify", alice.pk)


@pytest.mark.django_db
def test_certify_when_not_logged_in(otis):
    otis.get_30x("certify")


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
    otis.assert_has(resp, "Level 0")

    # Alice submits a problem set
    resp = otis.get_20x("submit-pset", alice.pk)
    otis.assert_has(resp, "Ready to submit?")

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
    otis.assert_has(resp, "13♣")
    otis.assert_has(resp, "37.0♥")
    otis.assert_has(resp, "This unit submission is pending review")

    # Alice should still be Level 0 though
    resp = otis.get_20x("stats", alice.pk)
    otis.assert_has(resp, "Level 0")

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
    otis.assert_has(resp, "content1.txt")

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
    otis.assert_has(resp, "This unit submission is pending review")
    otis.assert_has(resp, "13♣")
    otis.assert_has(resp, "3.7♥")

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
    otis.assert_has(resp, "Level 0")

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
    otis.assert_has(resp, "This unit submission is pending review")
    otis.assert_has(resp, "13♣")
    otis.assert_has(resp, "3.7♥")

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
    otis.assert_has(resp, "This unit submission was accepted")
    otis.assert_has(resp, "13♣")
    otis.assert_has(resp, "3.7♥")

    # Alice should show as leveled up now
    resp = otis.get_20x("stats", alice.pk)
    otis.assert_has(resp, "Level 4")

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
    otis.assert_has(resp, "This unit submission is pending review")
    otis.assert_has(resp, "100♣")
    otis.assert_has(resp, "20.0♥")

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
    otis.assert_has(resp, "Level 0")

    # simulate acceptance
    pset.status = "A"
    pset.save()

    # Alice is now Level 14
    resp = otis.get_20x("stats", alice.pk)
    otis.assert_has(resp, "Level 14")

    # check it shows up this way
    resp = otis.get_20x("pset", pset.pk)
    otis.assert_has(resp, "This unit submission was accepted")
    otis.assert_has(resp, "100♣")
    otis.assert_has(resp, "20.0♥")


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

    PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit1)
    PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit2)
    PSetFactory.create(student=eve, clubs=0, hours=0, status="A", unit=unit3)

    resp = otis.get_20x("student-pset-list", alice.pk)
    otis.assert_has(resp, unit1.code)
    otis.assert_has(resp, unit2.code)
    otis.assert_not_has(resp, unit3.code)


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
def test_file_operations(otis):
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)
    unit = UnitFactory.create(code="BMW")
    alice.curriculum.set([unit])
    alice.unlocked_units.add(unit)

    content = StringIO("Something")
    content.name = "content.txt"

    # upload a file
    resp = otis.post_20x(
        "uploads",
        alice.pk,
        unit.pk,
        data={"category": "scripts", "content": content, "description": "woof"},
    )

    messages = [m.message for m in resp.context["messages"]]
    assert "New file has been uploaded." in messages

    # invalid upload  ofa file
    resp = otis.post_20x(
        "uploads",
        alice.pk,
        unit.pk,
        data={"category": "invalid", "content": content, "description": "woof"},
    )

    messages = [m.message for m in resp.context["messages"]]
    assert "New file has been uploaded." not in messages

    upload = UploadedFile.objects.filter(benefactor=alice, unit=unit).first()

    assert upload is not None

    assert upload.unit == unit
    assert upload.owner == alice.user

    pk = upload.pk

    content1 = StringIO("Now with double the something!")
    content1.name = "content1.txt"
    # modify the file
    resp = otis.post_20x(
        "edit-file",
        upload.pk,
        data={"category": "scripts", "content": content1, "description": "bark"},
        follow=True,
    )

    upload = UploadedFile.objects.filter(pk=pk).first()
    assert upload is not None
    assert upload.description == "bark"

    otis.post_40x("delete-file", upload.pk)
    assert UploadedFile.objects.filter(pk=pk).exists()
    otis.login(UserFactory.create(is_staff=True))
    otis.post_20x("delete-file", upload.pk, follow=True)
    assert not UploadedFile.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_update_and_delete(otis) -> None:
    semester = SemesterFactory.create(active=True)
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)
    unit = UnitFactory.create(code="BMW")
    otis.post_denied("uploads", alice.pk, unit.pk, follow=True)
    alice.curriculum.set([unit])
    alice.unlocked_units.add(unit)

    # upload a file
    content = StringIO("Something")
    content.name = "content.txt"
    otis.post_20x(
        "uploads",
        alice.pk,
        unit.pk,
        data={"category": "scripts", "content": content, "description": "woof"},
        follow=True,
    )
    upload = UploadedFile.objects.get(benefactor=alice, unit=unit)

    # make sure Eve can't do anything
    eve = StudentFactory.create(semester=semester)
    otis.login(eve)
    malicious_content = StringIO("Now with double the something!")
    malicious_content.name = "malicous_content.txt"
    otis.post_denied(
        "edit-file",
        upload.pk,
        data={
            "category": "scripts",
            "content": malicious_content,
            "description": "bark",
        },
        follow=True,
    )
    otis.post_denied(
        "delete-file",
        upload.pk,
        data={
            "category": "scripts",
            "content": malicious_content,
            "description": "bark",
        },
        follow=True,
    )

    otis.login(alice)
    new_content = StringIO("Look I solved another problem")
    new_content.name = "new_content.txt"
    otis.post_20x(
        "edit-file",
        upload.pk,
        data={
            "category": "scripts",
            "content": new_content,
            "description": "meow",
        },
        follow=True,
    )
    upload.refresh_from_db()
    assert upload.description == "meow"


@pytest.mark.django_db
def test_index(otis):
    user = UserFactory.create()
    otis.login(user)

    # 0 Students
    resp = otis.get_20x("index")

    otis.assert_has(resp, "But nobody came.")

    # But now they are staff!
    user.is_staff = True
    user.save()
    resp = otis.get_20x("index")
    otis.assert_has(
        resp,
        "You're a staff member, so if you're expecting to see something, contact Evan.",
    )
    user.is_staff = False
    user.save()

    semester = SemesterFactory.create()
    RegistrationContainerFactory.create(semester=semester)
    resp = otis.get_20x("index")
    otis.assert_has(resp, "If you've already gotten your acceptance letter")

    StudentRegistrationFactory.create(user=user)
    resp = otis.get_20x("index")
    otis.assert_has(
        resp, "so you'll need to wait for Evan to confirm your registration"
    )

    alice = StudentFactory.create(user=user)
    otis.get_redirects(reverse("portal", args=(alice.pk,)), "index", follow=True)

    assistant = AssistantFactory.create()
    alice.assistant = assistant
    alice.save()
    bob = StudentFactory.create(assistant=assistant)

    otis.login(assistant)
    resp = otis.get_20x("index")
    otis.assert_has(resp, bob.name)


@pytest.mark.django_db
def test_past(otis):
    prevSemester = SemesterFactory.create(active=False)
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    prevAlice = StudentFactory.create(semester=prevSemester, user=alice.user)

    resp = otis.get_20x("past")
    otis.assert_has(resp, "Previous year listing")
    otis.assert_has(resp, prevSemester.name)
    otis.assert_has(resp, prevAlice.name)

    unit = UnitFactory.create(code="BMX")
    PSetFactory.create(
        student=prevAlice, clubs=0, hours=1501, status="A", unit=unit
    )

    resp = otis.get_20x("past", prevSemester.pk)
    otis.assert_has(resp, 38)
    otis.assert_has(resp, "Previous year listing")
    otis.assert_has(resp, prevSemester.name)
    otis.assert_has(resp, prevAlice.name)

    assistant = AssistantFactory.create()
    prevAlice.assistant = assistant
    prevAlice.save()
    bob = StudentFactory.create(assistant=assistant, semester=prevSemester)

    otis.login(assistant)
    resp = otis.get_20x("past", prevSemester.pk)
    otis.assert_has(resp, 38)
    otis.assert_has(resp, "Previous year listing")
    otis.assert_has(resp, prevSemester.name)
    otis.assert_has(resp, prevAlice.name)
    otis.assert_has(resp, bob.name)


@pytest.mark.django_db
def test_semester_list(otis):
    prevSemester = SemesterFactory.create(active=False)
    semester = SemesterFactory.create()

    user = UserFactory.create()
    alice = StudentFactory.create(semester=semester, user=user)
    otis.login(alice)

    resp = otis.get_20x("semester-list")
    otis.assert_has(resp, prevSemester.name)
    otis.assert_not_has(resp, "<th>Students</th>")

    user.is_superuser = True
    user.save()

    resp = otis.get_20x("semester-list")
    otis.assert_has(resp, prevSemester.name)
    otis.assert_has(resp, "<th>Students</th>")


@pytest.mark.django_db
def test_idle_warn(otis):
    user = UserFactory.create()
    user.is_staff = True
    user.save()
    otis.login(user)

    unit = UnitFactory.create(code="BMX")

    alice = StudentFactory.create(assistant=AssistantFactory.create(user=user))

    with freeze_time("2021-07-01", tz_offset=0):
        PSetFactory.create(
            student=alice, clubs=0, hours=1501, status="A", unit=unit
        )

    with freeze_time("2021-07-29", tz_offset=0):
        resp = otis.get_20x("idlewarn")

    otis.assert_has(resp, "Idle-warn")
    otis.assert_has(resp, "Lv. 38")
    otis.assert_has(resp, alice.user.email)
    otis.assert_has(resp, "28.00d")


@pytest.mark.django_db
def test_download_list(otis):
    semester = SemesterFactory.create()
    alice = StudentFactory.create(semester=semester)
    otis.login(alice)

    download = SemesterDownloadFileFactory.create(semester=semester)

    otis.get_40x("downloads", alice.pk + 1)
    resp = otis.get_20x("downloads", alice.pk)

    otis.assert_has(resp, download.content)


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
    otis.assert_not_has(resp, "request secret units")

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
    otis.assert_has(resp, "request secret units")

    # make sure the level up does its job
    messages = [m.message for m in resp.context["messages"]]
    assert "You leveled up! You're now level 9." in messages
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
    assert f"Added bonus unit {desired_unit} for you." in messages
    assert "There are no secret units you can request yet." not in messages
    alice.refresh_from_db()
    assert alice.curriculum.filter(pk=desired_unit.pk).exists()
