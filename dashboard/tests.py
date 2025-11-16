import datetime
import os
from io import StringIO

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
from otisweb_testsuite import EvanTestCase
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


class TestPortal(EvanTestCase):
    def test_portal_invoice_redirect(self):
        semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
        )
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        with freeze_time("2021-06-20", tz_offset=0):
            InvoiceFactory.create(student=alice)

        with freeze_time("2021-07-30", tz_offset=0):
            self.assertGetRedirects(
                reverse("invoice", args=(alice.pk,)), "portal", alice.pk, follow=True
            )

    def test_portal(self):
        semester = SemesterFactory.create(exam_family="Waltz")
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

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
        self.login(assistant)
        with freeze_time("2021-07-01", tz_offset=0):
            resp = self.assertGet20X("portal", alice.pk, follow=True)
        messages = [m.message for m in resp.context["messages"]]
        self.assertNotIn("You leveled up! You're now level 22.", messages)

        self.login(alice)
        with freeze_time("2021-07-01", tz_offset=0):
            resp = self.assertGet20X("portal", alice.pk, follow=True)

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("You leveled up! You're now level 22.", messages)

        # static stuff
        self.assertHas(resp, f"{alice.name} ({alice.semester.name})")
        self.assertHas(resp, 501)
        self.assertHas(resp, 2020)
        self.assertHas(resp, unit.code)
        self.assertHas(resp, test)
        self.assertHas(resp, quiz)

        # TODO check for whether meters are being rendered?

    def test_get_news(self):
        semester = SemesterFactory.create(exam_family="Waltz")
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

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
            self.assertEqual(len(news["announcements"]), 1)
            self.assertEqual(len(news["downloads"]), 1)
            self.assertEqual(len(news["markets"]), 1)
            self.assertEqual(len(news["hanabis"]), 1)
            self.assertEqual(len(news["opals"]), 1)

        with freeze_time("2021-07-30", tz_offset=0):
            news = get_news(alice_profile, alice)
            self.assertEqual(len(news["announcements"]), 0)
            self.assertEqual(len(news["downloads"]), 0)
            self.assertEqual(len(news["markets"]), 0)
            self.assertEqual(len(news["hanabis"]), 0)
            self.assertEqual(len(news["opals"]), 1)

        # alice dismisses stuff
        alice_profile.last_notif_dismiss = datetime.datetime(2021, 7, 2, tzinfo=UTC)
        alice_profile.save()

        with freeze_time("2021-07-02", tz_offset=0):
            news = get_news(alice_profile, alice)
            self.assertEqual(len(news["announcements"]), 0)
            self.assertEqual(len(news["downloads"]), 0)
            self.assertEqual(len(news["markets"]), 0)
            self.assertEqual(len(news["hanabis"]), 0)
            self.assertEqual(len(news["opals"]), 0)

        with freeze_time("2022-07-02", tz_offset=0):
            SemesterDownloadFileFactory.create(semester=semester)
            news = get_news(alice_profile, alice)
            self.assertEqual(len(news["announcements"]), 0)
            self.assertEqual(len(news["downloads"]), 1)
            self.assertEqual(len(news["markets"]), 2)
            self.assertEqual(len(news["hanabis"]), 2)
            self.assertEqual(len(news["opals"]), 0)


class TestAnnounce(EvanTestCase):
    def test_announcements(self):
        AnnouncementFactory.create(slug="one", content="하나")
        AnnouncementFactory.create(slug="two", content="둘")
        AnnouncementFactory.create(slug="three", content="셋")

        # First make sure nothing is accessible to outside world
        mallory = UserFactory.create(username="mallory")
        self.login(mallory)
        self.assertGet40X("announcement-list")
        self.assertGet40X("announcement-detail", "one")
        self.assertGet40X("announcement-detail", "two")
        self.assertGet40X("announcement-detail", "three")

        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(username="alice", groups=(verified_group,))
        self.login(alice)
        self.assertContains(self.assertGet20X("announcement-list"), "one")
        self.assertContains(self.assertGet20X("announcement-detail", "one"), "하나")
        self.assertContains(self.assertGet20X("announcement-detail", "two"), "둘")
        self.assertContains(self.assertGet20X("announcement-detail", "three"), "셋")


class TestCertify(EvanTestCase):
    def test_certify(self):
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        unit = UnitFactory.create(code="BMX")
        alice.curriculum.set([unit])
        alice.unlocked_units.add(unit)

        PSetFactory.create(student=alice, clubs=0, hours=1501, status="A", unit=unit)
        Level.objects.create(name="Level Thirty Eight", threshold=38)

        checksum = alice.get_checksum(settings.CERT_HASH_KEY)

        resp = self.assertGetRedirects(
            reverse(
                "certify",
                args=(
                    alice.pk,
                    checksum,
                ),
            ),
            "certify",
            follow=True,
        )

        self.assertHas(resp, 1501)
        self.assertHas(resp, 38)
        self.assertHas(resp, "Level Thirty Eight")

        self.assertGetDenied("certify", alice.pk, "invalid")
        self.assertGet20X("certify", alice.pk, checksum)

        eve = StudentFactory.create(semester=semester)
        self.login(eve)
        self.assertGetDenied("certify", alice.pk)

    def test_certify_when_not_logged_in(self):
        self.assertGet30X("certify")


class TestPSet(EvanTestCase):
    def test_submit_permissions(self):
        # delinquent

        semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
        )
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        with freeze_time("2021-06-20", tz_offset=0):
            InvoiceFactory.create(student=alice)

        with freeze_time("2021-07-30", tz_offset=0):
            self.assertGetDenied("submit-pset", alice.pk)

        # unenabled
        bob = StudentFactory.create(enabled=False)
        self.login(bob)

        self.assertGetDenied("submit-pset", bob.pk)

        # inactive semester
        carl = StudentFactory.create(semester=SemesterFactory.create(active=False))
        self.login(carl)

        self.assertGetDenied("submit-pset", carl.pk)

    def test_submit(self):
        unit1 = UnitFactory.create(code="BMW")
        unit2 = UnitFactory.create(code="DMX")
        unit3 = UnitFactory.create(code="ZMY")
        alice = StudentFactory.create()
        self.login(alice)
        alice.unlocked_units.add(unit1)
        alice.curriculum.set([unit1, unit2, unit3])

        # Alice should show initially as Level 0
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 0")

        # Alice submits a problem set
        resp = self.assertGet20X("submit-pset", alice.pk)
        self.assertHas(resp, "Ready to submit?")

        content1 = StringIO("Meow")
        content1.name = "content1.txt"
        resp = self.assertPost20X(
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
        self.assertHas(resp, "13♣")
        self.assertHas(resp, "37.0♥")
        self.assertHas(resp, "This unit submission is pending review")

        # Alice should still be Level 0 though
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 0")

        # Check pset reflects this data
        pset = PSet.objects.get(student=alice, unit=unit1)
        self.assertEqual(pset.clubs, 13)
        self.assertEqual(pset.hours, 37)
        self.assertEqual(pset.feedback, "hello")
        self.assertEqual(pset.special_notes, "meow")
        self.assertEqual(os.path.basename(pset.upload.content.name), "content1.txt")
        self.assertFalse(pset.accepted)
        self.assertFalse(pset.resubmitted)

        # Alice realizes she made a typo in hours and edits the problem set
        resp = self.assertGet20X("resubmit-pset", alice.pk)
        self.assertHas(resp, "content1.txt")

        content2 = StringIO("Purr")
        content2.name = "content2.txt"
        resp = self.assertPost20X(
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
        self.assertHas(resp, "This unit submission is pending review")
        self.assertHas(resp, "13♣")
        self.assertHas(resp, "3.7♥")

        # Check the updated problem set object
        pset = PSet.objects.get(student=alice, unit=unit1)
        self.assertEqual(pset.clubs, 13)
        self.assertEqual(pset.hours, 3.7)
        self.assertEqual(pset.feedback, "hello")
        self.assertEqual(pset.special_notes, "meow")
        self.assertEqual(os.path.basename(pset.upload.content.name), "content2.txt")
        self.assertFalse(pset.accepted)
        self.assertFalse(pset.resubmitted)

        # Alice should still be Level 0 though
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 0")

        # update again, but this time change just the metadata
        resp = self.assertPost20X(
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
        self.assertHas(resp, "This unit submission is pending review")
        self.assertHas(resp, "13♣")
        self.assertHas(resp, "3.7♥")

        # Check the updated problem set object
        pset = PSet.objects.get(student=alice, unit=unit1)
        self.assertEqual(pset.clubs, 13)
        self.assertEqual(pset.hours, 3.7)
        self.assertEqual(pset.feedback, "good day")
        self.assertEqual(pset.special_notes, "purr")
        self.assertEqual(os.path.basename(pset.upload.content.name), "content2.txt")
        self.assertFalse(pset.accepted)
        self.assertFalse(pset.resubmitted)

        # simulate acceptance
        pset.status = "A"
        pset.save()
        alice.unlocked_units.remove(unit1)
        alice.unlocked_units.add(unit2)
        alice.curriculum.set([unit1, unit2, unit3])

        # check it shows up this way
        resp = self.assertGet20X("pset", pset.pk)
        self.assertHas(resp, "This unit submission was accepted")
        self.assertHas(resp, "13♣")
        self.assertHas(resp, "3.7♥")

        # Alice should show as leveled up now
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 4")

        # now let's say Alice resubmits
        content3 = StringIO("Rawr")
        content3.name = "content3.txt"
        resp = self.assertPost20X(
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
        resp = self.assertGet20X("pset", pset.pk)
        self.assertHas(resp, "This unit submission is pending review")
        self.assertHas(resp, "100♣")
        self.assertHas(resp, "20.0♥")

        # Check the problem set
        pset = PSet.objects.get(student=alice, unit=unit1)
        self.assertEqual(pset.clubs, 100)
        self.assertEqual(pset.hours, 20)
        self.assertEqual(pset.feedback, "hello")
        self.assertEqual(pset.special_notes, "meow")
        self.assertEqual(os.path.basename(pset.upload.content.name), "content3.txt")
        self.assertFalse(pset.accepted)
        self.assertTrue(pset.resubmitted)

        # Alice is now back to Level 0
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 0")

        # simulate acceptance
        pset.status = "A"
        pset.save()

        # Alice is now Level 14
        resp = self.assertGet20X("stats", alice.pk)
        self.assertHas(resp, "Level 14")

        # check it shows up this way
        resp = self.assertGet20X("pset", pset.pk)
        self.assertHas(resp, "This unit submission was accepted")
        self.assertHas(resp, "100♣")
        self.assertHas(resp, "20.0♥")

    def test_unit_query(self):
        units = UnitFactory.create_batch(size=20)
        alice = StudentFactory.create()
        alice.curriculum.set(units[:18])
        alice.unlocked_units.set(units[4:7])
        for unit in units[:4]:
            PSetFactory.create(student=alice, unit=unit)
        PSetFactory.create(student=alice, unit=units[4], status="P")

        self.assertEqual(get_units_to_submit(alice).count(), 2)
        self.assertEqual(get_units_to_unlock(alice).count(), 11)

    def test_pset_list(self):
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        eve = StudentFactory.create(semester=semester)

        unit1 = UnitFactory.create(code="BMW")
        unit2 = UnitFactory.create(code="ZMX")
        unit3 = UnitFactory.create(code="DAY")

        PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit1)
        PSetFactory.create(student=alice, clubs=0, hours=0, status="A", unit=unit2)
        PSetFactory.create(student=eve, clubs=0, hours=0, status="A", unit=unit3)

        resp = self.assertGet20X("student-pset-list", alice.pk)
        self.assertHas(resp, unit1.code)
        self.assertHas(resp, unit2.code)
        self.assertNotHas(resp, unit3.code)

    def test_pset_list_permission(self):
        semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
        )
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        with freeze_time("2021-06-20", tz_offset=0):
            InvoiceFactory.create(student=alice)

        with freeze_time("2021-07-30", tz_offset=0):
            self.assertGetDenied("student-pset-list", alice.pk)

        eve = StudentFactory.create(semester=semester)

        self.login(eve)

        self.assertGet20X("student-pset-list", eve.pk)
        self.assertGetDenied("student-pset-list", alice.pk)

    def test_file_operations(self):
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)
        unit = UnitFactory.create(code="BMW")
        alice.curriculum.set([unit])
        alice.unlocked_units.add(unit)

        content = StringIO("Something")
        content.name = "content.txt"

        # upload a file
        resp = self.assertPost20X(
            "uploads",
            alice.pk,
            unit.pk,
            data={"category": "scripts", "content": content, "description": "woof"},
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("New file has been uploaded.", messages)

        # invalid upload  ofa file
        resp = self.assertPost20X(
            "uploads",
            alice.pk,
            unit.pk,
            data={"category": "invalid", "content": content, "description": "woof"},
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertNotIn("New file has been uploaded.", messages)

        upload = UploadedFile.objects.filter(benefactor=alice, unit=unit).first()

        assert upload is not None

        self.assertTrue(upload.unit == unit)
        self.assertTrue(upload.owner == alice.user)

        pk = upload.pk

        content1 = StringIO("Now with double the something!")
        content1.name = "content1.txt"
        # modify the file
        resp = self.assertPost20X(
            "edit-file",
            upload.pk,
            data={"category": "scripts", "content": content1, "description": "bark"},
            follow=True,
        )

        upload = UploadedFile.objects.filter(pk=pk).first()
        assert upload is not None
        self.assertTrue(upload.description == "bark")

        self.assertPost40X("delete-file", upload.pk)
        self.assertTrue(UploadedFile.objects.filter(pk=pk).exists())
        self.login(UserFactory.create(is_staff=True))
        self.assertPost20X("delete-file", upload.pk, follow=True)
        self.assertFalse(UploadedFile.objects.filter(pk=pk).exists())

    def test_update_and_delete(self) -> None:
        semester = SemesterFactory.create(active=True)
        alice = StudentFactory.create(semester=semester)
        self.login(alice)
        unit = UnitFactory.create(code="BMW")
        self.assertPostDenied("uploads", alice.pk, unit.pk, follow=True)
        alice.curriculum.set([unit])
        alice.unlocked_units.add(unit)

        # upload a file
        content = StringIO("Something")
        content.name = "content.txt"
        self.assertPost20X(
            "uploads",
            alice.pk,
            unit.pk,
            data={"category": "scripts", "content": content, "description": "woof"},
            follow=True,
        )
        upload = UploadedFile.objects.get(benefactor=alice, unit=unit)

        # make sure Eve can't do anything
        eve = StudentFactory.create(semester=semester)
        self.login(eve)
        malicious_content = StringIO("Now with double the something!")
        malicious_content.name = "malicous_content.txt"
        self.assertPostDenied(
            "edit-file",
            upload.pk,
            data={
                "category": "scripts",
                "content": malicious_content,
                "description": "bark",
            },
            follow=True,
        )
        self.assertPostDenied(
            "delete-file",
            upload.pk,
            data={
                "category": "scripts",
                "content": malicious_content,
                "description": "bark",
            },
            follow=True,
        )

        self.login(alice)
        new_content = StringIO("Look I solved another problem")
        new_content.name = "new_content.txt"
        self.assertPost20X(
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
        self.assertEqual(upload.description, "meow")


class TestList(EvanTestCase):
    def test_index(self):
        user = UserFactory.create()
        self.login(user)

        # 0 Students
        resp = self.assertGet20X("index")

        self.assertHas(resp, "But nobody came.")

        # But now they are staff!
        user.is_staff = True
        user.save()
        resp = self.assertGet20X("index")
        self.assertHas(
            resp,
            "You're a staff member, so if you're expecting to see something, contact Evan.",
        )
        user.is_staff = False
        user.save()

        semester = SemesterFactory.create()
        RegistrationContainerFactory.create(semester=semester)
        resp = self.assertGet20X("index")
        self.assertHas(resp, "If you've already gotten your acceptance letter")

        StudentRegistrationFactory.create(user=user)
        resp = self.assertGet20X("index")
        self.assertHas(
            resp, "so you'll need to wait for Evan to confirm your registration"
        )

        alice = StudentFactory.create(user=user)
        self.assertGetRedirects(
            reverse("portal", args=(alice.pk,)), "index", follow=True
        )

        assistant = AssistantFactory.create()
        alice.assistant = assistant
        alice.save()
        bob = StudentFactory.create(assistant=assistant)

        self.login(assistant)
        resp = self.assertGet20X("index")
        self.assertHas(resp, bob.name)

    def test_past(self):
        prevSemester = SemesterFactory.create(active=False)
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        prevAlice = StudentFactory.create(semester=prevSemester, user=alice.user)

        resp = self.assertGet20X("past")
        self.assertHas(resp, "Previous year listing")
        self.assertHas(resp, prevSemester.name)
        self.assertHas(resp, prevAlice.name)

        unit = UnitFactory.create(code="BMX")
        PSetFactory.create(
            student=prevAlice, clubs=0, hours=1501, status="A", unit=unit
        )

        resp = self.assertGet20X("past", prevSemester.pk)
        self.assertHas(resp, 38)
        self.assertHas(resp, "Previous year listing")
        self.assertHas(resp, prevSemester.name)
        self.assertHas(resp, prevAlice.name)

        assistant = AssistantFactory.create()
        prevAlice.assistant = assistant
        prevAlice.save()
        bob = StudentFactory.create(assistant=assistant, semester=prevSemester)

        self.login(assistant)
        resp = self.assertGet20X("past", prevSemester.pk)
        self.assertHas(resp, 38)
        self.assertHas(resp, "Previous year listing")
        self.assertHas(resp, prevSemester.name)
        self.assertHas(resp, prevAlice.name)
        self.assertHas(resp, bob.name)

    def test_semester_list(self):
        prevSemester = SemesterFactory.create(active=False)
        semester = SemesterFactory.create()

        user = UserFactory.create()
        alice = StudentFactory.create(semester=semester, user=user)
        self.login(alice)

        resp = self.assertGet20X("semester-list")
        self.assertHas(resp, prevSemester.name)
        self.assertNotHas(resp, "<th>Students</th>")

        user.is_superuser = True
        user.save()

        resp = self.assertGet20X("semester-list")
        self.assertHas(resp, prevSemester.name)
        self.assertHas(resp, "<th>Students</th>")

    def test_idle_warn(self):
        user = UserFactory.create()
        user.is_staff = True
        user.save()
        self.login(user)

        unit = UnitFactory.create(code="BMX")

        alice = StudentFactory.create(assistant=AssistantFactory.create(user=user))

        with freeze_time("2021-07-01", tz_offset=0):
            PSetFactory.create(
                student=alice, clubs=0, hours=1501, status="A", unit=unit
            )

        with freeze_time("2021-07-29", tz_offset=0):
            resp = self.assertGet20X("idlewarn")

        self.assertHas(resp, "Idle-warn")
        self.assertHas(resp, "Lv. 38")
        self.assertHas(resp, alice.user.email)
        self.assertHas(resp, "28.00d")

    def test_download_list(self):
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        download = SemesterDownloadFileFactory.create(semester=semester)

        self.assertGet40X("downloads", alice.pk + 1)
        resp = self.assertGet20X("downloads", alice.pk)

        self.assertHas(resp, download.content)


class TestLevelUpAndBonus(EvanTestCase):
    def test_level_up_and_bonus(self) -> None:
        semester = SemesterFactory.create()
        alice = StudentFactory.create(semester=semester)
        self.login(alice)

        secret4 = UnitGroupFactory.create(name="Level 4", subject="K", hidden=True)
        secret9 = UnitGroupFactory.create(name="Level 9", subject="K", hidden=True)
        secret16 = UnitGroupFactory.create(name="Level 16", subject="K", hidden=True)
        for group in (secret4, secret9, secret16):
            for code in ("BKV", "DKV", "ZKV"):
                UnitFactory.create(code=code, group=group)
        BonusLevelFactory.create(level=4, group=secret4)
        BonusLevelFactory.create(level=9, group=secret9)
        BonusLevelFactory.create(level=16, group=secret16)

        resp = self.assertGet20X("portal", alice.pk, follow=True)
        self.assertNotHas(resp, "request secret units")

        # the form shouldn't have anything in the queryset right now
        resp = self.assertGet20X("bonus-level-request", alice.pk, follow=True)
        self.assertEqual(resp.context["form"].fields["unit"].queryset.count(), 0)
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("There are no secret units you can request yet.", messages)

        # set Alice's level by adding a unit
        PSetFactory.create(
            student=alice,
            clubs=13,
            hours=37,
            status="A",
            unit__code="BCY",
        )
        resp = self.assertGet20X("portal", alice.pk, follow=True)
        self.assertHas(resp, "request secret units")

        # make sure the level up does its job
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("You leveled up! You're now level 9.", messages)
        alice.refresh_from_db()
        self.assertEqual(alice.last_level_seen, 9)
        self.assertEqual(alice.curriculum.all().count(), 2)
        self.assertEqual(alice.curriculum.all()[0].code, "BKV")
        self.assertEqual(alice.curriculum.all()[1].code, "BKV")

        # now there should be six choices in the form
        resp = self.assertGet20X("bonus-level-request", alice.pk, follow=True)
        messages = [m.message for m in resp.context["messages"]]
        self.assertNotIn("There are no secret units you can request yet.", messages)
        queryset = resp.context["form"].fields["unit"].queryset
        self.assertEqual(queryset.count(), 6)
        self.assertQuerySetEqual(
            queryset,
            Unit.objects.filter(group__in=(secret4, secret9)),  # type: ignore
            ordered=False,
        )

        # let's submit one and make sure it works
        desired_unit = Unit.objects.get(group=secret9, code="DKV")
        self.assertTrue(queryset.filter(pk=desired_unit.pk).exists())
        self.assertFalse(alice.curriculum.filter(pk=desired_unit.pk).exists())
        resp = self.assertPost20X(
            "bonus-level-request",
            alice.pk,
            data={"unit": desired_unit.pk},
            follow=True,
        )
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(f"Added bonus unit {desired_unit} for you.", messages)
        self.assertNotIn("There are no secret units you can request yet.", messages)
        alice.refresh_from_db()
        self.assertTrue(alice.curriculum.filter(pk=desired_unit.pk).exists())
