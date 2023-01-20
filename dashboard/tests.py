import os
from io import StringIO

from core.factories import UnitFactory
from core.factories import SemesterFactory
from django.utils import timezone
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import StudentFactory

from dashboard.factories import PSetFactory
from dashboard.models import PSet
from dashboard.models import UploadedFile
from dashboard.utils import get_units_to_submit, get_units_to_unlock

utc = timezone.utc


class TestSubmitPSet(EvanTestCase):
    def test_submit(self) -> None:
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

    def test_queryset(self) -> None:
        units = UnitFactory.create_batch(size=20)
        alice = StudentFactory.create()
        alice.curriculum.set(units[0:18])
        alice.unlocked_units.set(units[4:7])
        for unit in units[0:4]:
            PSetFactory.create(student=alice, unit=unit)
        PSetFactory.create(student=alice, unit=units[4], status="P")

        self.assertEqual(get_units_to_submit(alice).count(), 2)
        self.assertEqual(get_units_to_unlock(alice).count(), 11)

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
        self.assertPost20X("delete-file", upload.pk, follow=True)
        self.assertFalse(UploadedFile.objects.filter(pk=upload.pk).exists())
