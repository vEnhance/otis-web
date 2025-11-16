from hashlib import sha256

from django.contrib.auth.models import User
from django.test.utils import override_settings

from arch.factories import HintFactory, ProblemFactory
from arch.models import Hint, Problem
from core.factories import SemesterFactory, UnitFactory, UserFactory, UserProfileFactory
from dashboard.factories import PSetFactory
from dashboard.models import Announcement
from otisweb_testsuite import EvanTestCase
from hanabi.factories import HanabiContestFactory, HanabiPlayerFactory
from hanabi.models import HanabiParticipation, HanabiReplay
from opal.factories import OpalPuzzleFactory
from payments.factories import PaymentLogFactory
from roster.factories import (
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
    UnitInquiryFactory,
)
from roster.models import ApplyUUID, Invoice, Student, UnitInquiry

EXAMPLE_PASSWORD = "take just the first 24"
TARGET_HASH = sha256(EXAMPLE_PASSWORD.encode("ascii")).hexdigest()


@override_settings(API_TARGET_HASH=TARGET_HASH)
class TestAincradWithSetup(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        active_semester = SemesterFactory.create(name="New")
        old_semester = SemesterFactory.create(name="Old", active=False)

        alice = StudentFactory.create(
            user__first_name="Alice",
            user__last_name="Aardvárk",
            user__username="alice",
            user__email="alice@example.org",
            semester=active_semester,
        )
        bob = StudentFactory.create(
            user__first_name="Bôb B.",
            user__last_name="Bèta",
            user__username="bob",
            user__email="bob@example.org",
            semester=active_semester,
        )
        carol = StudentFactory.create(
            user__first_name="Carol",
            user__last_name="Cutie",
            user__username="carol",
            user__email="carol@example.org",
            semester=active_semester,
        )
        david = StudentFactory.create(
            user__first_name="David",
            user__last_name="Darling",
            user__username="david",
            user__email="david@example.org",
            semester=active_semester,
        )
        eve = StudentFactory.create(
            user__first_name="Eve",
            user__last_name="Edgeworth",
            user__username="eve",
            user__email="edge@wor.th",
            semester=active_semester,
        )
        UserProfileFactory.create(user=alice.user, email_on_announcement=True)
        UserProfileFactory.create(user=bob.user, email_on_announcement=True)
        UserProfileFactory.create(user=carol.user, email_on_announcement=True)
        UserProfileFactory.create(user=david.user, email_on_announcement=False)
        UserProfileFactory.create(user=eve.user, email_on_announcement=True)
        old_alice = StudentFactory.create(user=alice.user, semester=old_semester)

        submitted_unit, requested_unit = UnitFactory.create_batch(2)
        PSetFactory.create(
            student=alice,
            unit=submitted_unit,
            next_unit_to_unlock=requested_unit,
            clubs=120,
            hours=37,
            status="P",
            feedback="Meow",
            special_notes="Purr",
        )
        PSetFactory.create_batch(2, student=bob, status="P")
        PSetFactory.create_batch(3, student=carol, status="P")
        PSetFactory.create_batch(7, student=alice, status="A")
        PSetFactory.create_batch(2, student=alice, status="R")
        PSetFactory.create_batch(4, student=alice, status="P")
        PSetFactory.create_batch(3, student=david, status="A")
        PSetFactory.create_batch(4, student=old_alice, status="A")
        PSetFactory.create_batch(2, student=old_alice, status="P")

        UnitInquiryFactory.create_batch(
            5, student=alice, action_type="INQ_ACT_UNLOCK", status="INQ_ACC"
        )
        UnitInquiryFactory.create_batch(
            2, student=alice, action_type="INQ_ACT_DROP", status="INQ_ACC"
        )
        UnitInquiryFactory.create_batch(
            3, student=alice, action_type="INQ_ACT_UNLOCK", status="INQ_NEW"
        )

        alice.curriculum.add(submitted_unit)
        alice.curriculum.add(requested_unit)
        alice.unlocked_units.add(submitted_unit)

        InvoiceFactory.create(student=alice, total_paid=250)
        InvoiceFactory.create(student=bob)
        invC = InvoiceFactory.create(student=carol, total_paid=210)
        invD = InvoiceFactory.create(student=david, total_paid=480)
        invE = InvoiceFactory.create(student=eve, total_paid=1)
        PaymentLogFactory.create(invoice=invC, amount=50)
        PaymentLogFactory.create(invoice=invC, amount=70)
        PaymentLogFactory.create(invoice=invC, amount=90)
        PaymentLogFactory.create(invoice=invC, amount=9001, refunded=True)
        PaymentLogFactory.create(invoice=invD, amount=360)
        PaymentLogFactory.create(invoice=invD, amount=120)
        PaymentLogFactory.create(invoice=invE, amount=1)
        PaymentLogFactory.create(invoice=invC, amount=9001, refunded=True)

        regcontainer_active = RegistrationContainerFactory.create(
            semester=active_semester
        )
        regcontainer_old = RegistrationContainerFactory.create(semester=old_semester)

        for student in (alice, bob, carol, david, eve, old_alice):
            StudentRegistrationFactory.create(
                user=student.user,
                container=(
                    regcontainer_active
                    if student.semester.active is True
                    else regcontainer_old
                ),
                processed=True,
            )
        new_user = UserFactory.create(
            username="frisk", first_name="Frank", last_name="Frisk"
        )
        StudentRegistrationFactory.create(
            user=new_user, container=regcontainer_active, processed=False
        )

    def test_init(self):
        resp = self.assertPost20X(
            "api",
            json={
                "action": "init",
                "token": EXAMPLE_PASSWORD,
            },
        )
        out = resp.json()
        self.assertEqual(out["_name"], "Root")
        self.assertEqual(len(out["_children"][0]["_children"]), 12)
        self.assertIn("timestamp", out)
        self.assertEqual(len(out.keys()), 4)

        pset_data = out["_children"][0]
        self.assertEqual(pset_data["_name"], "Problem sets")

        for pset in pset_data["_children"]:
            if pset["feedback"] == "Meow":
                self.assertEqual(pset["status"], "P")
                self.assertEqual(pset["clubs"], 120)
                self.assertEqual(pset["hours"], 37)
                self.assertEqual(pset["feedback"], "Meow")
                self.assertEqual(pset["special_notes"], "Purr")
                self.assertEqual(pset["student__user__first_name"], "Alice")
                self.assertEqual(pset["num_accepted_all"], 11)
                self.assertEqual(pset["num_accepted_current"], 7)
                break
        else:
            self.fail("Could not find Alice's pset0 in aincrad test")
        for pset in pset_data["_children"]:
            if pset["student__user__first_name"] == "Bôb B.":
                self.assertEqual(pset["status"], "P")
                self.assertEqual(pset["num_accepted_all"], 0)
                self.assertEqual(pset["num_accepted_current"], 0)
                break
        else:
            self.fail("Could not find a pset from Bôb B. in aincrad test")

        inquiries = out["_children"][1]["inquiries"]
        self.assertEqual(len(inquiries), 3)
        self.assertEqual(inquiries[0]["unlock_inquiry_count"], 8)

        regs = out["_children"][4]["registrations"]
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["user__first_name"], "Frank")
        self.assertEqual(regs[0]["user__last_name"], "Frisk")

    def test_invoice(self):
        out = self.assertPost20X(
            "api",
            json={
                "action": "invoice",
                "token": EXAMPLE_PASSWORD,
                "field": "adjustment",
                "entries": {
                    "alice.aardvark": -240,
                    "edge@wor.th": -474,
                    "l.lawliet": 1337,
                },
            },
        ).json()
        self.assertEqual(out["updated_count"], 2)
        self.assertCountEqual(
            out["updated_names_list"],
            ["Alice Aardvárk <alice@example.org>", "Eve Edgeworth <edge@wor.th>"],
        )
        self.assertEqual(len(out["entries_remaining"]), 1)
        self.assertIn("l.lawliet", out["entries_remaining"])

        out = self.assertPost20X(
            "api",
            json={
                "action": "invoice",
                "token": EXAMPLE_PASSWORD,
                "field": "extras",
                "entries": {
                    Student.objects.get(
                        user__first_name="Alice", semester__active=True
                    ).pk: 10,
                    "david.darling": 10,
                    "mihael.keehl": -9001,
                },
            },
        ).json()
        self.assertEqual(out["updated_count"], 2)
        self.assertCountEqual(
            out["updated_names_list"],
            ["Alice Aardvárk <alice@example.org>", "David Darling <david@example.org>"],
        )
        self.assertEqual(len(out["entries_remaining"]), 1)
        self.assertIn("mihael.keehl", out["entries_remaining"])

        out = self.assertPost20X(
            "api",
            json={
                "action": "invoice",
                "token": EXAMPLE_PASSWORD,
                "field": "total_paid",
                "entries": {
                    "alice.aardvark": 250,
                    "bob.beta": 480,
                    Student.objects.get(
                        user__first_name="Carol", user__last_name="Cutie"
                    ).pk: 110,
                    "eve.edgeworth": 5,
                    "nate.river": 1152,
                },
            },
        ).json()
        self.assertEqual(out["updated_count"], 3)
        self.assertCountEqual(
            out["updated_names_list"],
            [
                "Bôb B. Bèta <bob@example.org>",
                "Carol Cutie <carol@example.org>",
                "Eve Edgeworth <edge@wor.th>",
            ],
        )
        self.assertEqual(len(out["entries_remaining"]), 1)
        self.assertIn("nate.river", out["entries_remaining"])

        # check the invoices are correct
        invoice_alice = Invoice.objects.get(student__user__first_name="Alice")
        invoice_bob = Invoice.objects.get(student__user__first_name="Bôb B.")
        invoice_carol = Invoice.objects.get(student__user__first_name="Carol")
        invoice_david = Invoice.objects.get(student__user__first_name="David")
        invoice_eve = Invoice.objects.get(student__user__first_name="Eve")

        self.assertAlmostEqual(invoice_alice.adjustment, -240)
        self.assertAlmostEqual(invoice_alice.extras, 10)
        self.assertAlmostEqual(invoice_alice.total_paid, 250)

        self.assertAlmostEqual(invoice_bob.adjustment, 0)
        self.assertAlmostEqual(invoice_bob.extras, 0)
        self.assertAlmostEqual(invoice_bob.total_paid, 480)

        self.assertAlmostEqual(invoice_carol.adjustment, 0)
        self.assertAlmostEqual(invoice_carol.extras, 0)
        self.assertAlmostEqual(invoice_carol.total_paid, 320)

        self.assertAlmostEqual(invoice_david.adjustment, 0)
        self.assertAlmostEqual(invoice_david.extras, 10)
        self.assertAlmostEqual(invoice_david.total_paid, 480)

        self.assertAlmostEqual(invoice_eve.adjustment, -474)
        self.assertAlmostEqual(invoice_eve.extras, 0)
        self.assertAlmostEqual(invoice_eve.total_paid, 6)

    def test_accept_inquiries(self) -> None:
        resp = self.assertPost20X(
            "api",
            json={
                "action": "accept_inquiries",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["result"], "success")
        self.assertEqual(resp.json()["count"], 3)
        self.assertEqual(len(UnitInquiry.objects.filter(status="INQ_NEW")), 0)

    def test_accept_registrations(self) -> None:
        n = len(Student.objects.all())
        frisk = User.objects.get(username="frisk")
        self.assertFalse(frisk.groups.filter(name="Verified").exists())
        self.assertFalse(Student.objects.filter(user__username="frisk").exists())
        resp = self.assertPost20X(
            "api",
            json={
                "action": "accept_registrations",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["result"], "success")
        self.assertEqual(resp.json()["count"], 1)
        self.assertEqual(len(Student.objects.all()), n + 1)
        self.assertTrue(Student.objects.filter(user__username="frisk").exists())
        self.assertTrue(frisk.groups.filter(name="Verified").exists())

    def test_email(self) -> None:
        resp = self.assertPost20X(
            "api",
            json={
                "action": "email_list",
                "token": EXAMPLE_PASSWORD,
            },
        )
        students = resp.json()["students"]
        self.assertEqual(len(students), 4)
        for s in students:
            if s["user__username"] == "eve":
                self.assertEqual(s["user__email"], "edge@wor.th")
            else:
                for x in ("alice", "bob", "carol"):
                    if s["user__username"] == x:
                        self.assertEqual(s["user__email"], f"{x}@example.org")
                        break
                else:
                    raise ValueError


@override_settings(API_TARGET_HASH=TARGET_HASH)
class TestAincrad(EvanTestCase):
    def test_failed_auth(self):
        resp = self.assertPost40X(
            "api",
            json={
                "action": "init",
                "token": "this wrong password is not a puzzle",
            },
        )
        self.assertEqual(resp.status_code, 418)

    def test_get_add_hints(self):
        HintFactory.create_batch(10)

        resp = self.assertPost20X(
            "api",
            json={
                "action": "get_hints",
                "puid": "18SLA7",
                "token": EXAMPLE_PASSWORD,
            },
        )
        out = resp.json()
        self.assertEqual(len(out["hints"]), 0)

        A7_Hints = Hint.objects.filter(problem__puid="18SLA7")

        resp = self.assertPost20X(
            "api",
            json={
                "action": "add_hints",
                "puid": "18SLA7",
                "content": "get",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertIn("pk", resp.json())
        self.assertEqual(resp.json()["number"], 0)
        resp = self.assertPost20X(
            "api",
            json={
                "action": "add_hints",
                "puid": "18SLA7",
                "content": "good",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertIn("pk", resp.json())
        self.assertEqual(resp.json()["number"], 10)

        resp = self.assertPost20X(
            "api",
            json={
                "action": "get_hints",
                "puid": "18SLA7",
                "token": EXAMPLE_PASSWORD,
            },
        )
        out = resp.json()
        self.assertEqual(len(out["hints"]), 2)
        self.assertTrue(A7_Hints.filter(number=0, content="get").exists())
        self.assertTrue(A7_Hints.filter(number=10, content="good").exists())

        resp = self.assertPost20X(
            "api",
            json={
                "action": "add_many_hints",
                "allow_delete_hints": False,
                "puid": "18SLA7",
                "new_hints": [
                    {"number": 80, "content": "80%", "keywords": "eighty"},
                    {"number": 90, "content": "90%", "keywords": "ninety"},
                    {"number": 70, "content": "70%", "keywords": "seventy"},
                ],
                "old_hints": list(
                    A7_Hints.values(
                        "keywords",
                        "pk",
                        "number",
                        "content",
                    )
                ),
                "token": EXAMPLE_PASSWORD,
            },
        )
        out = resp.json()
        self.assertEqual(len(out["pks"]), 3)
        self.assertEqual(out["num_deletes"], 0)
        self.assertTrue(
            A7_Hints.filter(number=80, content="80%", keywords="eighty").exists()
        )
        self.assertTrue(
            A7_Hints.filter(number=70, content="70%", keywords="seventy").exists()
        )
        self.assertTrue(
            A7_Hints.filter(number=90, content="90%", keywords="ninety").exists()
        )

        # try and fail to delete hints
        self.assertPost40X(
            "api",
            json={
                "action": "add_many_hints",
                "allow_delete_hints": False,
                "puid": "18SLA7",
                "new_hints": [],
                "old_hints": [],
                "token": EXAMPLE_PASSWORD,
            },
        )

        # OK, so at this point we have, what, 5 hints?
        # alright let's edit some more
        resp = self.assertPost20X(
            "api",
            json={
                "action": "add_many_hints",
                "allow_delete_hints": True,
                "puid": "18SLA7",
                "new_hints": [
                    {"number": 100, "content": "100%", "keywords": "hundred"}
                ],
                "old_hints": [
                    {
                        "pk": A7_Hints.get(number=80).pk,
                        "number": 85,
                        "content": "Updated 85%",
                        "keywords": "updated",
                    },
                    {
                        "pk": A7_Hints.get(number=90).pk,
                        "number": 95,
                        "content": "Updated 95%",
                        "keywords": "updated",
                    },
                ],
                "token": EXAMPLE_PASSWORD,
            },
        )
        out = resp.json()
        self.assertEqual(len(out["pks"]), 1)
        self.assertEqual(out["num_deletes"], 3)  # 0%, 10%, 70%
        self.assertEqual(set(A7_Hints.values_list("number", flat=True)), {85, 95, 100})
        self.assertEqual(A7_Hints.filter(keywords="updated").count(), 2)
        self.assertEqual(A7_Hints.filter(keywords__startswith="Updated").count(), 2)

    def test_arch_url_update(self) -> None:
        ProblemFactory.create(
            puid="19USEMO1",
            hyperlink="https://aops.com/community/p15412066",
        )
        ProblemFactory.create(
            puid="19USEMO2",
            hyperlink="https://aops.com/community/p15412166",
        )
        ProblemFactory.create(
            puid="19USEMO3",
            hyperlink="https://wrong.url.to.fix/",
        )
        ProblemFactory.create(
            puid="19USEMO4",
            hyperlink="https://aops.com/community/p15425708",
        )
        ProblemFactory.create(
            puid="19USEMO5",
            hyperlink="https://aops.com/community/p15425728",
        )
        ProblemFactory.create(
            puid="19USEMO6",
        )

        resp = self.assertPost20X(
            "api",
            json={
                "action": "arch_url_update",
                "urls": {
                    "19USEMO3": "https://aops.com/community/p15412083",
                    "19USEMO5": "https://aops.com/community/p15425728",
                    "19USEMO6": "https://aops.com/community/p15425714",
                    "18SLA7": "https://aops.com/community/p12752777",
                },
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["updated_count"], 2)
        self.assertEqual(resp.json()["created_count"], 1)
        self.assertEqual(
            Problem.objects.get(puid="19USEMO3").hyperlink,
            "https://aops.com/community/p15412083",
        )
        self.assertEqual(
            Problem.objects.get(puid="19USEMO6").hyperlink,
            "https://aops.com/community/p15425714",
        )
        self.assertEqual(
            Problem.objects.get(puid="18SLA7").hyperlink,
            "https://aops.com/community/p12752777",
        )

    def test_hanabi_contest(self) -> None:
        HANABI_PLAYERS = (
            "alsodqed",
            "anotherplayer1",
            "dqed",
            "dupe1",
            "dupe2",
            "dupe3",
            "player1",
            "player2",
            "player3",
            "runnerup1",
            "runnerup2",
            "winner1",
            "winner2",
            "winner3",
        )
        for u in HANABI_PLAYERS:
            HanabiPlayerFactory.create(hanab_username=u)
        contest = HanabiContestFactory.create(
            variant_id=1,
            variant_name="4 Suits",
            num_suits=4,
        )

        resp = self.assertPost20X(
            "api",
            json={
                "action": "hanabi_results",
                "pk": contest.pk,
                "replays": [
                    {
                        "players": ["winner1", "winner2", "winner3"],
                        "turn_count": 42,
                        "game_score": 20,
                        "replay_id": 812,
                    },
                    {
                        "players": ["runnerup1", "runnerup2", "dqed"],
                        "turn_count": 44,
                        "game_score": 20,
                        "replay_id": 811,
                    },
                    {
                        "players": ["player3", "player2", "player1"],
                        "turn_count": 45,
                        "game_score": 15,
                        "replay_id": 271,
                    },
                    {
                        "players": ["dupe1", "dupe2", "dupe3"],
                        "turn_count": 46,
                        "game_score": 13,
                        "replay_id": 920989,
                    },
                    {
                        "players": ["dupe1", "dupe2", "dupe3"],
                        "turn_count": 46,
                        "game_score": 12,
                        "replay_id": 920982,
                    },
                    {
                        "players": ["alsodqed", "anotherplayer1", "dqed"],
                        "turn_count": 8,
                        "game_score": 1,
                        "replay_id": 798,
                    },
                    {
                        "players": ["dupe1", "dupe2", "dupe3"],
                        "turn_count": 28,
                        "game_score": 7,
                        "replay_id": 920998,
                    },
                    {
                        "players": ["dupe2", "alsodqed", "dupe3"],
                        "turn_count": 43,
                        "game_score": 11,
                        "replay_id": 921020,
                    },
                ],
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(
            {r["replay_id"] for r in resp.json()["replays"]},
            {798, 811, 812, 271},
        )
        self.assertEqual(len(resp.json()["names"]), 9)
        self.assertAlmostEqual(
            HanabiReplay.objects.get(replay_id=812).spades_score, 6.0
        )
        self.assertAlmostEqual(
            HanabiReplay.objects.get(replay_id=811).spades_score, 5.0
        )
        self.assertAlmostEqual(
            HanabiReplay.objects.get(replay_id=271).spades_score, 1.265625
        )
        self.assertEqual(HanabiParticipation.objects.all().count(), 9)
        self.assertEqual(
            HanabiParticipation.objects.filter(replay__replay_id=812).count(), 3
        )
        self.assertEqual(
            HanabiParticipation.objects.filter(replay__replay_id=811).count(), 2
        )
        self.assertEqual(
            HanabiParticipation.objects.filter(replay__replay_id=271).count(), 3
        )
        self.assertEqual(
            HanabiParticipation.objects.filter(replay__replay_id=798).count(), 1
        )
        self.assertEqual(
            set(
                HanabiParticipation.objects.all().values_list(
                    "player__hanab_username", flat=True
                )
            ),
            {
                "anotherplayer1",
                "player1",
                "player2",
                "player3",
                "runnerup1",
                "runnerup2",
                "winner1",
                "winner2",
                "winner3",
            },
        )

        contest.refresh_from_db()
        self.assertTrue(contest.processed)

    def test_grade_problem_set(self) -> None:
        unit = UnitFactory.create()
        alice_user = UserFactory.create()

        pset1 = PSetFactory.create(
            student__user=alice_user,
            student__semester__active=False,
            unit=unit,
            eligible=False,
            status="A",
        )
        pset2 = PSetFactory.create(
            student__user=alice_user,
            student__semester__active=False,
            unit=unit,
            eligible=True,
            status="A",
        )
        pset3 = PSetFactory.create(student__user=alice_user, unit=unit, status="P")

        resp = self.assertPost20X(
            "api",
            json={
                "pk": pset3.pk,
                "action": "grade_problem_set",
                "token": EXAMPLE_PASSWORD,
                "status": "A",
                "staff_comments": "Good job",
            },
        )
        self.assertEqual(resp.json()["result"], "success")

        pset1.refresh_from_db()
        pset2.refresh_from_db()
        pset3.refresh_from_db()
        self.assertFalse(pset1.eligible)
        self.assertFalse(pset2.eligible)
        self.assertTrue(pset3.eligible)
        self.assertEqual(pset1.status, "A")
        self.assertEqual(pset2.status, "A")
        self.assertEqual(pset3.status, "A")
        self.assertEqual(pset3.staff_comments, "Good job")

    def test_announcement(self) -> None:
        self.assertFalse(Announcement.objects.all().exists())

        # Create a new announcement
        resp = self.assertPost20X(
            "api",
            json={
                "action": "announcement_write",
                "slug": "testing",
                "subject": "Testing 1",
                "content": "This is a sample **announcement**.",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["is_new"], True)
        self.assertEqual(Announcement.objects.all().count(), 1)
        a = Announcement.objects.get(slug="testing")
        self.assertEqual(a.subject, "Testing 1")
        self.assertEqual(
            a.content_rendered, "<p>This is a sample <strong>announcement</strong>.</p>"
        )

        # Update it
        resp = self.assertPost20X(
            "api",
            json={
                "action": "announcement_write",
                "slug": "testing",
                "subject": "Testing 2",
                "content": "Another update.",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["is_new"], False)
        self.assertEqual(Announcement.objects.all().count(), 1)
        a = Announcement.objects.get(slug="testing")
        self.assertEqual(a.subject, "Testing 2")
        self.assertEqual(a.content_rendered, "<p>Another update.</p>")

        # Create a third announcement
        resp = self.assertPost20X(
            "api",
            json={
                "action": "announcement_write",
                "slug": "thinking",
                "subject": "Deep in thought",
                "content": "Couldn't be me!",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(resp.json()["is_new"], True)
        self.assertEqual(Announcement.objects.all().count(), 2)
        a = Announcement.objects.get(slug="thinking")
        self.assertEqual(a.subject, "Deep in thought")
        self.assertEqual(a.content_rendered, "<p>Couldn't be me!</p>")

    def test_opal_handler(self) -> None:
        OpalPuzzleFactory.create(
            hunt__slug="teammate", slug="tetrogram", is_metapuzzle=True
        )
        resp = self.assertPost20X(
            "api",
            json={
                "action": "opal_list",
                "token": EXAMPLE_PASSWORD,
            },
        )
        self.assertEqual(len(resp.json()["puzzles"]), 1)
        puzzle_json = resp.json()["puzzles"][0]
        self.assertEqual(puzzle_json["hunt__slug"], "teammate")
        self.assertEqual(puzzle_json["slug"], "tetrogram")
        self.assertEqual(puzzle_json["is_metapuzzle"], True)

    def test_apply_uuid_handler(self) -> None:
        self.assertPost20X(
            "api",
            json={
                "action": "apply_uuid",
                "token": EXAMPLE_PASSWORD,
                "uuid": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",  # no that's not a diamond
                "percent_aid": 50,
            },
        )
        self.assertEqual(
            ApplyUUID.objects.filter(
                uuid="f81d4fae-7dec-11d0-a765-00a0c91e6bf6", percent_aid=50
            ).count(),
            1,
        )
