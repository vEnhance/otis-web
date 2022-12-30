from hashlib import sha256

from arch.factories import HintFactory
from arch.models import Hint
from core.factories import SemesterFactory, UnitFactory
from dashboard.factories import PSetFactory
from django.test.utils import override_settings
from evans_django_tools.testsuite import EvanTestCase
from payments.factories import PaymentLogFactory
from roster.factories import InvoiceFactory, StudentFactory, UnitInquiryFactory
from roster.models import Invoice, Student

EXAMPLE_PASSWORD = "take just the first 24"
TARGET_HASH = sha256(EXAMPLE_PASSWORD.encode("ascii")).hexdigest()


@override_settings(API_TARGET_HASH=TARGET_HASH)
class TestAincrad(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        active_semester = SemesterFactory.create(name="New")
        old_semester = SemesterFactory.create(name="Old", active=False)

        alice = StudentFactory.create(
            user__first_name="Alice",
            user__last_name="Aardvárk",
            semester=active_semester,
        )
        bob = StudentFactory.create(
            user__first_name="Bôb B.", user__last_name="Bèta", semester=active_semester
        )
        carol = StudentFactory.create(
            user__first_name="Carol", user__last_name="Cutie", semester=active_semester
        )
        david = StudentFactory.create(
            user__first_name="David",
            user__last_name="Darling",
            semester=active_semester,
        )
        eve = StudentFactory.create(
            user__first_name="Eve",
            user__last_name="Edgeworth",
            semester=active_semester,
        )
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
        PSetFactory.create_batch(3, status="A")
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
        PaymentLogFactory.create(invoice=invD, amount=360)
        PaymentLogFactory.create(invoice=invD, amount=120)
        PaymentLogFactory.create(invoice=invE, amount=1)

    def test_init(self):
        resp = self.post("api", json={"action": "init", "token": EXAMPLE_PASSWORD})
        self.assertResponse20X(resp)
        out = resp.json()
        self.assertEqual(out["_name"], "Root")
        self.assertEqual(len(out["_children"][0]["_children"]), 10)
        self.assertIn("timestamp", out)
        self.assertEqual(len(out.keys()), 3)

        pset_data = out["_children"][0]
        self.assertEqual(pset_data["_name"], "Problem sets")

        pset0 = pset_data["_children"][0]
        self.assertEqual(pset0["status"], "P")
        self.assertEqual(pset0["clubs"], 120)
        self.assertEqual(pset0["hours"], 37)
        self.assertEqual(pset0["feedback"], "Meow")
        self.assertEqual(pset0["special_notes"], "Purr")
        self.assertEqual(pset0["student__user__first_name"], "Alice")
        self.assertEqual(pset0["num_accepted_all"], 11)
        self.assertEqual(pset0["num_accepted_current"], 7)

        pset1 = pset_data["_children"][1]
        self.assertEqual(pset1["status"], "P")
        self.assertEqual(pset1["student__user__first_name"], "Bôb B.")
        self.assertEqual(pset1["num_accepted_all"], 0)
        self.assertEqual(pset1["num_accepted_current"], 0)

        inquiries = out["_children"][1]["inquiries"]
        self.assertEqual(len(inquiries), 3)
        self.assertEqual(inquiries[0]["unlock_inquiry_count"], 8)

    def test_invoice(self):
        out = self.assertPost20X(
            "api",
            json={
                "action": "invoice",
                "token": EXAMPLE_PASSWORD,
                "field": "adjustment",
                "entries": {
                    "alice.aardvark": -240,
                    "eve.edgeworth": -474,
                    "l.lawliet": 1337,
                },
            },
        ).json()
        self.assertEqual(out["updated_count"], 2)
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
                    Student.objects.get(user__first_name="Carol").pk: 110,
                    "eve.edgeworth": 5,
                    "nate.river": 1152,
                },
            },
        ).json()
        self.assertEqual(out["updated_count"], 3)
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

    def test_get_add_hints(self):
        HintFactory.create_batch(10)

        resp = self.post("api", json={"action": "get_hints", "puid": "18SLA7"})
        self.assertResponse20X(resp)
        out = resp.json()
        self.assertEqual(len(out["hints"]), 0)

        A7_Hints = Hint.objects.filter(problem__puid="18SLA7")

        resp = self.assertPost20X(
            "api",
            json={
                "action": "add_hints",
                "puid": "18SLA7",
                "content": "get",
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
            },
        )
        self.assertIn("pk", resp.json())
        self.assertEqual(resp.json()["number"], 10)

        resp = self.post("api", json={"action": "get_hints", "puid": "18SLA7"})
        self.assertResponse20X(resp)
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
            },
        )
        out = resp.json()
        self.assertEqual(len(out["pks"]), 1)
        self.assertEqual(out["num_deletes"], 3)  # 0%, 10%, 70%
        self.assertEqual(set(A7_Hints.values_list("number", flat=True)), {85, 95, 100})
        self.assertEqual(A7_Hints.filter(keywords="updated").count(), 2)
        self.assertEqual(A7_Hints.filter(keywords__startswith="Updated").count(), 2)
