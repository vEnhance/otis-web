import datetime
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from freezegun.api import freeze_time

from core.factories import (
    SemesterFactory,
    UnitFactory,
    UnitGroupFactory,
    UserFactory,
    UserProfileFactory,
)
from core.models import Semester, Unit, UnitGroup, UserProfile
from dashboard.factories import PSetFactory
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from roster.models import (
    Assistant,
    Invoice,
    RegistrationContainer,
    Student,
    StudentRegistration,
    UnitInquiry,
)

from .admin import build_students

UTC = datetime.timezone.utc


class RosterGeneralTest(EvanTestCase):
    def test_username_lookup(self) -> None:
        admin: User = UserFactory.create(is_superuser=True, is_staff=True)
        semester_old: Semester = SemesterFactory.create(end_year=2025)
        semester_new: Semester = SemesterFactory.create(end_year=2026)
        bob: User = UserFactory.create(username="bob")
        StudentFactory.create(user=bob, semester=semester_old)
        bob_new: Student = StudentFactory.create(user=bob, semester=semester_new)

        self.login(admin)
        self.assertGetNotFound("username-lookup", "carl")

        self.assertRedirects(
            self.get("username-lookup", "bob"),
            bob_new.get_absolute_url(),
        )

    def test_email_lookup(self) -> None:
        admin: User = UserFactory.create(is_superuser=True, is_staff=True)
        regular_user: User = UserFactory.create()
        semester_old: Semester = SemesterFactory.create(end_year=2025)
        semester_new: Semester = SemesterFactory.create(end_year=2026)

        # Create students with different emails and semesters
        alice: User = UserFactory.create(email="alice@example.com")
        StudentFactory.create(user=alice, semester=semester_old)
        alice_new: Student = StudentFactory.create(user=alice, semester=semester_new)

        bob: User = UserFactory.create(email="bob@example.com")
        bob_student: Student = StudentFactory.create(user=bob, semester=semester_new)

        # Test access control - anonymous user should be redirected
        self.assertGet30X("email-lookup")

        # Test access control - regular user should be denied
        self.login(regular_user)
        self.assertGet40X("email-lookup")

        # Test GET request with admin user - should show form
        self.login(admin)
        resp = self.assertGet20X("email-lookup")
        self.assertHas(resp, "Email lookup")

        # Test POST with valid email that matches a student (should redirect)
        self.assertRedirects(
            self.post("email-lookup", data={"email": "alice@example.com"}),
            alice_new.get_absolute_url(),
        )

        # Test POST with valid email but no matching student (should show warning)
        resp = self.assertPost20X(
            "email-lookup", data={"email": "nonexistent@example.com"}, follow=True
        )
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("No matches found", messages)

        # Test POST with invalid email format (form validation should catch it)
        resp = self.assertPost20X(
            "email-lookup",
            data={"email": "invalid_email"},
        )
        # Form should be re-displayed with errors, no redirect should occur
        self.assertHas(resp, "Email lookup")

        # Test case insensitive matching
        self.assertRedirects(
            self.post("email-lookup", data={"email": "BOB@EXAMPLE.COM"}),
            bob_student.get_absolute_url(),
        )

    def test_update_profile(self) -> None:
        alice: User = UserFactory.create()
        self.login(alice)

        self.assertGet20X("update-profile")

        first_name = alice.first_name
        last_name = alice.last_name
        email = alice.email

        invalid_resp = self.assertPost20X(
            "update-profile",
            data={
                "first_name": f"a{first_name}",
                "last_name": f"a{last_name}",
                "email": "invalid_Email!!",
            },
        )

        messages = [m.message for m in invalid_resp.context["messages"]]
        self.assertNotIn("Your information has been updated.", messages)

        same_email_resp = self.assertPost20X(
            "update-profile",
            data={
                "first_name": f"a{first_name}",
                "last_name": f"a{last_name}",
                "email": email,
            },
        )

        messages = [m.message for m in same_email_resp.context["messages"]]
        self.assertIn("Your information has been updated.", messages)

        resp = self.assertPost20X(
            "update-profile",
            data={
                "first_name": f"a{first_name}",
                "last_name": f"a{last_name}",
                "email": f"1{email}",
            },
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("Your information has been updated.", messages)

        alice.refresh_from_db()
        self.assertTrue(f"a{first_name}" == alice.first_name)
        self.assertTrue(f"a{last_name}" == alice.last_name)
        self.assertTrue(f"1{email}" == alice.email)

    def test_mystery(self) -> None:
        mysteryGroup: UnitGroup = UnitGroupFactory.create(name="Mystery")
        mystery: Unit = UnitFactory(group=mysteryGroup)  # type: ignore
        added_unit: Unit = UnitFactory.create_batch(2)[1]  # next two units

        alice: Student = StudentFactory.create()
        self.login(alice)

        self.assertResponseDenied(
            self.client.get("/roster/mystery-unlock/easier/", follow=True)
        )

        alice.curriculum.set([mystery])
        alice.unlocked_units.set([mystery])

        self.assertResponse20X(
            resp := self.client.get("/roster/mystery-unlock/harder/", follow=True)
        )

        self.assertFalse(alice.curriculum.contains(mystery))
        self.assertFalse(alice.unlocked_units.contains(mystery))

        self.assertTrue(alice.curriculum.contains(added_unit))
        self.assertTrue(alice.unlocked_units.contains(added_unit))

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(f"Added the unit {added_unit}", messages)

    def test_giga_chart(self) -> None:
        semester: Semester = SemesterFactory.create(show_invoices=True)
        students: list[Student] = [
            StudentFactory.create(
                reg=StudentRegistrationFactory.create(), semester=semester
            )
            for _ in range(0, 30)
        ]

        for student in students:
            InvoiceFactory.create(student=student)
            UserProfileFactory.create(user=student.user)

        admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)
        self.login(admin)
        self.assertGet20X("giga-chart", "csv", follow=True)

        resp = self.assertGet20X("giga-chart", "html", follow=True)
        for student in students:
            for prop in [
                student.name,
                student.user.email,
                student.reg.parent_email,
            ]:
                self.assertContains(resp, prop)


class AssistantTest(EvanTestCase):
    def test_student_assistant_list(self) -> None:
        for i in range(1, 6):
            asst: Assistant = AssistantFactory.create(
                user__first_name=f"F{i}",
                user__last_name=f"L{i}",
                user__email=f"user{i}@evanchen.cc",
                shortname=f"Short{i}",
            )
            StudentFactory.create_batch(
                i * i, user__first_name="GoodKid", assistant=asst
            )
        StudentFactory.create(user__first_name="BadKid")
        staff: User = UserFactory.create(is_staff=True)
        self.login(staff)
        resp = self.assertGet20X("instructors")
        for i in range(1, 6):
            self.assertHas(resp, f'"F{i} L{i}"')
            self.assertHas(resp, f"user{i}@evanchen.cc")
        self.assertHas(resp, "GoodKid", count=2 * (1 + 4 + 9 + 16 + 25))
        self.assertHas(resp, r"&lt;user5@evanchen.cc&gt;")
        self.assertNotHas(resp, "BadKid")
        self.assertNotHas(resp, "out of sync")  # only admins can see the sync button

        admin: User = UserFactory.create(is_staff=True, is_superuser=True)
        self.login(admin)
        resp = self.assertGet20X("instructors")
        self.assertHas(resp, "out of sync")

        group = Group.objects.get(name="Active Staff")
        qs: QuerySet[User] = group.user_set.all()  # type: ignore
        self.assertEqual(qs.count(), 0)

        resp = self.assertPostOK("instructors")
        self.assertEqual(qs.count(), 5)
        self.assertNotHas(resp, "out of sync")
        resp = self.assertGetOK("instructors")
        self.assertNotHas(resp, "out of sync")

        self.login(staff)
        self.assertPost40X("instructors")  # staff can't post

    def test_advance(self) -> None:
        assist: Assistant = AssistantFactory.create()
        alice: Student = StudentFactory.create(assistant=assist)

        self.login(alice)

        self.assertGetDenied("advance", alice.pk)

        units: list[Unit] = UnitFactory.create_batch(4)

        # unlock 0, add 1, lock 2, drop 3

        alice.curriculum.set(units[2:4])  # units 3 and 4
        alice.unlocked_units.set([units[3]])

        self.login(assist)

        self.assertGet20X("advance", alice.pk)

        invalid_resp = self.assertPost20X(
            "advance",
            alice.pk,
            data={
                "units_to_unlock": ["invalid"],
                "units_to_add": [units[1].pk],
                "units_to_lock": [units[2].pk],
                "units_to_drop": [units[3].pk],
            },
            follow=True,
        )
        messages = [m.message for m in invalid_resp.context["messages"]]
        self.assertNotIn(
            "Successfully updated student.",
            messages,
        )

        resp = self.assertPost20X(
            "advance",
            alice.pk,
            data={
                "units_to_unlock": [units[0].pk],
                "units_to_add": [units[1].pk],
                "units_to_lock": [units[2].pk],
                "units_to_drop": [units[3].pk],
            },
            follow=True,
        )
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(
            "Successfully updated student.",
            messages,
        )

        alice.refresh_from_db()
        self.assertTrue(alice.unlocked_units.contains(units[0]))
        self.assertFalse(alice.unlocked_units.contains(units[1]))
        self.assertFalse(alice.unlocked_units.contains(units[3]))

        self.assertTrue(alice.curriculum.contains(units[0]))
        self.assertTrue(alice.curriculum.contains(units[1]))
        self.assertFalse(alice.unlocked_units.contains(units[2]))
        self.assertTrue(alice.curriculum.contains(units[2]))
        self.assertFalse(alice.curriculum.contains(units[3]))

    def test_link_assistant(self) -> None:
        assistant = AssistantFactory.create()
        assistant2 = AssistantFactory.create()
        alice = StudentFactory.create()
        StudentFactory.create()
        StudentFactory.create(assistant=assistant)
        StudentFactory.create(assistant=assistant2)

        self.assertGet30X("link-assistant")  # anonymous redirects to login
        self.login(UserFactory.create(is_staff=False))
        self.assertGet40X("link-assistant")

        self.login(assistant.user)
        resp = self.assertGetOK("link-assistant")
        self.assertEqual(len(resp.context["form"].fields["student"].queryset), 2)
        self.assertPostOK("link-assistant", data={"student": alice.pk})
        alice.refresh_from_db()
        self.assertEqual(alice.assistant.pk, assistant.pk)
        resp = self.assertGetOK("link-assistant")
        self.assertEqual(len(resp.context["form"].fields["student"].queryset), 1)


class CurriculumTest(EvanTestCase):
    def test_curriculum(self) -> None:
        staff: Assistant = AssistantFactory.create()
        alice: Student = StudentFactory.create(assistant=staff)

        unitgroups: list[UnitGroup] = UnitGroupFactory.create_batch(4)
        for unitgroup in unitgroups:
            for letter in "BDZ":
                UnitFactory.create(
                    code=letter + unitgroup.subject[0] + "W", group=unitgroup
                )

        self.login(alice)
        self.assertHas(self.get("currshow", alice.pk), text="you are not an instructor")

        self.login(staff)
        self.assertNotHas(
            self.get("currshow", alice.pk), text="you are not an instructor"
        )

        invalid_data = {
            "group-0": [
                "invalid",
            ],
            "group-1": [4, 6],
            "group-3": [10, 11, 12],
        }
        resp = self.post("currshow", alice.pk, data=invalid_data)
        self.assertNotEqual(
            len(get_object_or_404(Student, pk=alice.pk).curriculum.all()), 6
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertNotIn(
            "Successfully saved curriculum of 6 units.",
            messages,
        )

        data = {
            "group-0": [
                1,
            ],
            "group-1": [4, 6],
            "group-3": [10, 11, 12],
        }
        resp = self.post("currshow", alice.pk, data=data)
        self.assertEqual(
            len(get_object_or_404(Student, pk=alice.pk).curriculum.all()), 6
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(
            "Successfully saved curriculum of 6 units.",
            messages,
        )

    def test_finalize(self) -> None:
        alice: Student = StudentFactory.create(newborn=True)
        self.login(alice)
        self.assertHas(
            self.post("finalize", alice.pk, data={"submit": True}, follow=True),
            "You should select some units",
        )
        units: list[Unit] = UnitFactory.create_batch(20)
        alice.curriculum.set(units)
        self.assertHas(
            self.post("finalize", alice.pk, data={}, follow=True),
            "Your curriculum has been finalized!",
        )
        self.assertEqual(alice.unlocked_units.count(), 3)
        self.assertPost40X("finalize", alice.pk, data={"submit": True})

    def test_student_properties(self) -> None:
        alice: Student = StudentFactory.create()
        units: list[Unit] = UnitFactory.create_batch(10)
        alice.curriculum.set(units[:7])
        alice.unlocked_units.set(units[2:5])
        self.assertEqual(alice.curriculum_length, 7)
        self.assertEqual(alice.num_unlocked, 3)

    def test_master_schedule(self) -> None:
        alice: Student = StudentFactory.create(
            user__first_name="Ada", user__last_name="Adalhaidis"
        )
        units: list[Unit] = UnitFactory.create_batch(10)
        alice.curriculum.set(units[:8])
        self.login(UserFactory.create(is_staff=True))
        self.assertHas(
            self.get("master-schedule"),
            text=f'title="{alice.user.first_name} {alice.user.last_name}"',
            count=8,
        )


class InquiryTest(EvanTestCase):
    def test_inquiry(self) -> None:
        firefly: Assistant = AssistantFactory.create()
        alice: Student = StudentFactory.create(assistant=firefly)
        units: list[Unit] = UnitFactory.create_batch(20)
        self.login(alice)

        # Check that an invalid unit is not processed
        invalid_resp = self.post(
            "inquiry",
            alice.pk,
            data={
                "unit": "invalid",
                "action_type": "INQ_ACT_UNLOCK",
                "explanation": "hi",
            },
        )
        self.assertNotHas(invalid_resp, "Petition automatically processed")

        with freeze_time("2025-10-29", tz_offset=0):
            # Alice unlocks 6 units, should be autoprocessed.
            for i in range(6):
                resp = self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[i].pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "hi",
                    },
                    follow=True,
                )
                self.assertHas(resp, "Petition automatically processed")
                inq = UnitInquiry.objects.get(
                    student=alice, unit=units[i].pk, action_type="INQ_ACT_UNLOCK"
                )
                self.assertTrue(inq.was_auto_processed)
                self.assertEqual(inq.status, "INQ_ACC")

            self.assertGet20X("inquiry", alice.pk, follow=True)

            # Now Alice has done 6 units, they shouldn't be able to get more
            # (This differs from production behavior because production also gives you a default three units)
            self.assertEqual(alice.curriculum.count(), 6)
            self.assertEqual(alice.unlocked_units.count(), 6)
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[19].pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "hi",
                    },
                    follow=True,
                ),
                "Petition submitted, wait for it!",
            )
            inq = UnitInquiry.objects.get(
                student=alice, unit=units[19].pk, action_type="INQ_ACT_UNLOCK"
            )
            self.assertFalse(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_NEW")

            self.assertEqual(alice.curriculum.count(), 6)
            self.assertEqual(alice.unlocked_units.count(), 6)

            # We have our assistant lock a unit
            self.login(firefly)
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[3].pk,
                        "action_type": "INQ_ACT_LOCK",
                        "explanation": "hi",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            self.assertEqual(alice.curriculum.count(), 6)
            self.assertEqual(alice.unlocked_units.count(), 5)
            inq = UnitInquiry.objects.get(
                student=alice, unit=units[3].pk, action_type="INQ_ACT_LOCK"
            )
            self.assertTrue(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_ACC")
            self.assertFalse(alice.unlocked_units.contains(units[3]))

            # Now dropping should be autoprocessed by Alice
            self.login(alice)
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[3].pk,
                        "action_type": "INQ_ACT_DROP",
                        "explanation": "hi",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            inq = UnitInquiry.objects.get(
                student=alice, unit=units[3].pk, action_type="INQ_ACT_DROP"
            )
            self.assertTrue(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_ACC")

            self.assertEqual(alice.curriculum.count(), 5)
            self.assertEqual(alice.unlocked_units.count(), 5)

        with freeze_time("2025-10-30", tz_offset=0):
            # We now give Alice some more units :o
            self.login(firefly)
            for i in range(6, 10):
                self.assertHas(
                    self.post(
                        "inquiry",
                        alice.pk,
                        data={
                            "unit": units[i].pk,
                            "action_type": "INQ_ACT_UNLOCK",
                            "explanation": "hi",
                        },
                        follow=True,
                    ),
                    "Petition automatically processed",
                )
                inq = UnitInquiry.objects.get(
                    student=alice, unit=units[i].pk, action_type="INQ_ACT_UNLOCK"
                )
                self.assertTrue(inq.was_auto_processed)
                self.assertEqual(inq.status, "INQ_ACC")
            self.assertEqual(alice.curriculum.count(), 9)
            self.assertEqual(alice.unlocked_units.count(), 9)

            # Check that you can't unlock more units when you are already at nine
            self.login(alice)
            for i in range(11, 14):
                self.assertHas(
                    self.post(
                        "inquiry",
                        alice.pk,
                        data={
                            "unit": units[i].pk,
                            "action_type": "INQ_ACT_UNLOCK",
                            "explanation": "hi",
                        },
                        follow=True,
                    ),
                    "more than 9 unfinished",
                )
                inq = UnitInquiry.objects.get(
                    student=alice, unit=units[i].pk, action_type="INQ_ACT_UNLOCK"
                )
                self.assertTrue(inq.was_auto_processed)
                self.assertEqual(inq.status, "INQ_REJ")
            self.assertEqual(alice.curriculum.count(), 9)
            self.assertEqual(alice.unlocked_units.count(), 9)

            # appending should be autoprocessed
            for i in range(15, 18):
                self.assertHas(
                    self.post(
                        "inquiry",
                        alice.pk,
                        data={
                            "unit": units[i].pk,
                            "action_type": "INQ_ACT_APPEND",
                            "explanation": "hi",
                        },
                        follow=True,
                    ),
                    "Petition automatically processed",
                )
                inq = UnitInquiry.objects.get(
                    student=alice, unit=units[i].pk, action_type="INQ_ACT_APPEND"
                )
                self.assertTrue(inq.was_auto_processed)
                self.assertEqual(inq.status, "INQ_ACC")
            self.assertEqual(alice.curriculum.count(), 12)
            self.assertEqual(alice.unlocked_units.count(), 9)

            # check that petitions are now locked because of abnormally large count
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[19].pk,
                        "action_type": "INQ_ACT_DROP",
                        "explanation": "hi",
                    },
                    follow=True,
                ),
                "abnormally large",
            )
            inq = UnitInquiry.objects.get(
                student=alice, unit=units[19].pk, action_type="INQ_ACT_DROP"
            )
            self.assertFalse(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_HOLD")

            # drop a bunch of units for alice
            self.login(firefly)
            for i in range(4, 14):
                self.assertHas(
                    self.post(
                        "inquiry",
                        alice.pk,
                        data={
                            "unit": units[i].pk,
                            "action_type": "INQ_ACT_DROP",
                            "explanation": "hi",
                        },
                        follow=True,
                    ),
                    "Petition automatically processed",
                )
                inq = UnitInquiry.objects.get(
                    student=alice, unit=units[i].pk, action_type="INQ_ACT_DROP"
                )
                self.assertTrue(inq.was_auto_processed)
                self.assertEqual(inq.status, "INQ_ACC")
            self.assertEqual(alice.curriculum.count(), 6)
            self.assertEqual(alice.unlocked_units.count(), 3)

        with freeze_time("2025-10-31", tz_offset=0):
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": units[5].pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "add back in",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            self.assertEqual(alice.curriculum.count(), 7)
            self.assertEqual(alice.unlocked_units.count(), 4)
            inq = UnitInquiry.objects.get(
                student=alice,
                unit=units[5].pk,
                action_type="INQ_ACT_UNLOCK",
                explanation="add back in",
            )
            self.assertTrue(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_ACC")

            # Alice hit the hold limit earlier, this just circumvents it.
            self.login(alice)
            PSetFactory.create_batch(30, student=alice)
            alice.save()

            # secret unit should be autoprocessed!
            secret_group = UnitGroupFactory.create(
                name="Spooky Unit", subject="K", hidden=True
            )
            secret_unit = UnitFactory.create(code="BKV", group=secret_group)
            alice.curriculum.add(secret_unit)

            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": secret_unit.pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "its almost halloween and my family wants to host it at our house.",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            self.assertEqual(alice.curriculum.count(), 8)
            self.assertEqual(alice.unlocked_units.count(), 5)
            inq = UnitInquiry.objects.get(
                student=alice, unit=secret_unit.pk, action_type="INQ_ACT_UNLOCK"
            )
            self.assertTrue(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_ACC")

            # check that autoprocessing old units works
            inactive_semester = SemesterFactory.create(active=False)
            inactive_alice = StudentFactory.create(
                semester=inactive_semester, user=alice.user
            )
            old_group = UnitGroupFactory.create(name="Last Year Unit", subject="A")
            old_unit = UnitFactory.create(code="BAW", group=old_group)
            inactive_alice.curriculum.add(old_unit)
            inactive_alice.unlocked_units.add(old_unit)
            self.assertEqual(inactive_alice.curriculum.count(), 1)
            self.assertEqual(inactive_alice.unlocked_units.count(), 1)
            inactive_alice.save()
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": old_unit.pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "did last year.",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            inq = UnitInquiry.objects.get(
                student=alice, unit=old_unit.pk, action_type="INQ_ACT_UNLOCK"
            )
            self.assertTrue(inq.was_auto_processed)
            self.assertEqual(inq.status, "INQ_ACC")
            self.assertEqual(alice.curriculum.count(), 9)
            self.assertEqual(alice.unlocked_units.count(), 6)

        # test a bunch of fail conditions
        bob: Student = StudentFactory.create(
            semester=SemesterFactory.create(active=False)
        )
        self.login(bob)
        self.assertGetDenied("inquiry", bob.pk)

        carl: Student = StudentFactory.create(enabled=False)
        self.login(carl)
        self.assertGetDenied("inquiry", carl.pk)

        dave: Student = StudentFactory.create(newborn=True)
        self.login(dave)
        self.assertGetDenied("inquiry", dave.pk)

        invoice_semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
        )
        eve = StudentFactory.create(semester=invoice_semester)
        self.login(eve)
        with freeze_time("2021-06-20", tz_offset=0):
            InvoiceFactory.create(student=eve)

        with freeze_time("2021-07-30", tz_offset=0):
            self.assertGetDenied("inquiry", eve.pk)

    def test_inquiry_cant_rapid_fire(self) -> None:
        with freeze_time("2025-10-31", tz_offset=0):
            alice = StudentFactory.create()
            unit = UnitFactory.create()
            self.login(alice)
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": unit.pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "unlock a unit",
                    },
                    follow=True,
                ),
                "Petition automatically processed",
            )
            self.assertHas(
                self.post(
                    "inquiry",
                    alice.pk,
                    data={
                        "unit": unit.pk,
                        "action_type": "INQ_ACT_UNLOCK",
                        "explanation": "accidentally pressed again because trigger happy",
                    },
                    follow=True,
                ),
                "The same petition already was submitted within the last 90 seconds.",
            )

    def test_cancel_inquiry_sets_status_to_canceled(self) -> None:
        alice = StudentFactory.create()
        unit = UnitFactory.create()
        inquiry = UnitInquiry.objects.create(
            student=alice,
            unit=unit,
            action_type="INQ_ACT_UNLOCK",
            status="INQ_NEW",
            explanation="Please unlock",
        )
        self.login(alice)
        resp = self.assertPost20X(
            "inquiry-cancel",
            inquiry.pk,
            follow=True,
        )
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, "INQ_CANC")
        self.assertHas(resp, "Inquiry successfully canceled.")

    def test_only_owner_or_staff_can_cancel(self):
        alice = StudentFactory.create()
        bob = StudentFactory.create()
        staff = UserFactory.create(is_staff=True, is_superuser=True)
        unit = UnitFactory.create()
        inquiry = UnitInquiry.objects.create(
            student=alice,
            unit=unit,
            action_type="INQ_ACT_UNLOCK",
            status="INQ_NEW",
            explanation="Please unlock",
        )
        # Bob cannot cancel Alice's inquiry
        self.login(bob)
        self.assertPost40X("inquiry-cancel", inquiry.pk)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, "INQ_NEW")  # Ensure status is still "INQ_NEW"

        # Staff can cancel
        self.login(staff)
        self.assertPost20X("inquiry-cancel", inquiry.pk, follow=True)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, "INQ_CANC")

    def test_cancel_button_only_for_pending(self):
        for status in ["INQ_ACC", "INQ_REJ", "INQ_HOLD", "INQ_CANC"]:
            alice = StudentFactory.create()
            unit = UnitFactory.create()
            UnitInquiry.objects.create(
                student=alice,
                unit=unit,
                action_type="INQ_ACT_UNLOCK",
                status=status,
                explanation="Test",
            )
            self.login(alice)
            self.assertGet20X("inquiry", alice.pk)

    def test_cannot_cancel_non_pending(self):
        alice = StudentFactory.create()
        unit = UnitFactory.create()
        for status in ["INQ_ACC", "INQ_REJ", "INQ_HOLD", "INQ_CANC"]:
            inquiry = UnitInquiry.objects.create(
                student=alice,
                unit=unit,
                action_type="INQ_ACT_UNLOCK",
                status=status,
                explanation="Test",
            )
            self.login(alice)
            self.assertPost40X("inquiry-cancel", inquiry.pk)
            inquiry.refresh_from_db()
            self.assertEqual(inquiry.status, status)


class InvoiceTest(EvanTestCase):
    def test_invoice(self) -> None:
        alice: Student = StudentFactory.create(semester__show_invoices=True)
        self.login(alice)
        InvoiceFactory.create(
            student=alice,
            preps_taught=2,
            hours_taught=8.4,
            adjustment=-30,
            credits=70,
            extras=100,
            total_paid=400,
        )
        response = self.get("invoice", follow=True)
        self.assertHas(response, "752.00")
        checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
        self.assertEqual(len(checksum), 36)
        self.assertHas(response, checksum)

    def test_delinquency(self) -> None:
        semester: Semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2022, 9, 21, tzinfo=UTC),
            most_payment_deadline=datetime.datetime(2023, 1, 21, tzinfo=UTC),
        )

        alice: Student = StudentFactory.create(semester=semester)

        self.assertEqual(alice.payment_status, 0)  # because no invoice exists
        with freeze_time("2022-08-05", tz_offset=0):
            invoice: Invoice = InvoiceFactory.create(
                student=alice,
                preps_taught=2,
            )

        # Alice has paid $0 so far
        self.assertEqual(invoice.total_owed, 480)
        with freeze_time("2022-09-05", tz_offset=0):
            self.assertEqual(alice.payment_status, 4)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-09-17", tz_offset=0):
            self.assertEqual(alice.payment_status, 1)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-09-25", tz_offset=0):
            self.assertEqual(alice.payment_status, 2)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-10-15", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
            invoice.forgive_date = datetime.datetime(2022, 10, 31, tzinfo=UTC)
            invoice.save()
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-11-15", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
        # Now suppose Alice makes the first payment
        invoice.total_paid = 240
        invoice.save()
        self.assertEqual(invoice.total_owed, 240)
        with freeze_time("2022-09-05", tz_offset=0):
            self.assertEqual(alice.payment_status, 4)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-09-17", tz_offset=0):
            self.assertEqual(alice.payment_status, 4)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-09-25", tz_offset=0):
            self.assertEqual(alice.payment_status, 4)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2022-10-15", tz_offset=0):
            self.assertEqual(alice.payment_status, 4)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2023-01-17", tz_offset=0):
            self.assertEqual(alice.payment_status, 5)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2023-01-25", tz_offset=0):
            self.assertEqual(alice.payment_status, 6)
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2023-02-15", tz_offset=0):
            self.assertEqual(alice.payment_status, 7)
            self.assertTrue(alice.is_delinquent)
            invoice.forgive_date = datetime.datetime(2023, 2, 28, tzinfo=UTC)
            invoice.save()
            self.assertFalse(alice.is_delinquent)
        with freeze_time("2023-06-05", tz_offset=0):
            self.assertEqual(alice.payment_status, 7)
            self.assertTrue(alice.is_delinquent)
        # Now suppose Alice makes the last payment
        invoice.total_paid = 480
        invoice.save()
        self.assertEqual(invoice.total_owed, 0)
        with freeze_time("2023-02-15", tz_offset=0):
            self.assertEqual(alice.payment_status, 0)
            self.assertFalse(alice.is_delinquent)

        bob: Student = StudentFactory.create(semester=semester)

        # Bob gets a bit of extra time to pay because he joined recently
        with freeze_time("2023-1-23", tz_offset=0):
            invoice2: Invoice = InvoiceFactory.create(
                student=bob,
                preps_taught=1,
            )
            self.assertEqual(bob.payment_status, 1)
            self.assertFalse(bob.is_delinquent)

        # Now he is affected
        semester.first_payment_deadline = datetime.datetime(2023, 1, 28, tzinfo=UTC)
        semester.save()

        with freeze_time("2023-2-08", tz_offset=0):
            self.assertEqual(bob.payment_status, 3)
            self.assertTrue(bob.is_delinquent)

        invoice2.total_paid = 120
        invoice2.save()

        with freeze_time("2023-2-08", tz_offset=0):
            self.assertEqual(bob.payment_status, 7)
            self.assertTrue(bob.is_delinquent)

        semester.most_payment_deadline = datetime.datetime(2023, 2, 21, tzinfo=UTC)
        semester.save()

        with freeze_time("2023-3-01", tz_offset=0):
            self.assertEqual(bob.payment_status, 7)
            self.assertTrue(bob.is_delinquent)

    def test_delinquency_for_joining_second_semester(self) -> None:
        semester: Semester = SemesterFactory.create(
            show_invoices=True,
            first_payment_deadline=datetime.datetime(2022, 9, 21, tzinfo=UTC),
            most_payment_deadline=datetime.datetime(2023, 1, 21, tzinfo=UTC),
            one_semester_date=datetime.datetime(2022, 12, 30, tzinfo=UTC),
        )

        alice: Student = StudentFactory.create(semester=semester)
        bob: Student = StudentFactory.create(semester=semester)
        self.assertEqual(alice.payment_status, 0)  # because no invoice exists
        self.assertEqual(bob.payment_status, 0)  # because no invoice exists
        with freeze_time("2022-08-05", tz_offset=0):
            InvoiceFactory.create(student=alice, preps_taught=2)
        with freeze_time("2023-01-01", tz_offset=0):
            InvoiceFactory.create(student=bob, preps_taught=1)

        with freeze_time("2023-01-02", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
            self.assertEqual(bob.payment_status, 4)
            self.assertFalse(bob.is_delinquent)

        with freeze_time("2023-01-20", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
            self.assertEqual(bob.payment_status, 1)
            self.assertFalse(bob.is_delinquent)

        with freeze_time("2023-01-25", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
            self.assertEqual(bob.payment_status, 2)
            self.assertFalse(bob.is_delinquent)

        with freeze_time("2023-01-30", tz_offset=0):
            self.assertEqual(alice.payment_status, 3)
            self.assertTrue(alice.is_delinquent)
            self.assertEqual(bob.payment_status, 3)
            self.assertTrue(bob.is_delinquent)

    def test_update_invoice(self) -> None:
        firefly: Assistant = AssistantFactory.create()
        alice: Student = StudentFactory.create(assistant=firefly)
        invoice: Invoice = InvoiceFactory.create(student=alice)
        self.login(firefly)
        self.assertGet20X("edit-invoice", alice.pk)
        self.assertPostRedirects(
            self.url("invoice", invoice.pk),
            "edit-invoice",
            invoice.pk,
            data={
                "preps_taught": 2,
                "hours_taught": 8.4,
                "adjustment": 0,
                "extras": 0,
                "total_paid": 1152,
                "credits": 0,
            },
        )


class RegTest(EvanTestCase):
    def test_reg(self) -> None:
        semester: Semester = SemesterFactory.create()

        # registration should redirect if there's no container yet
        alice: User = UserFactory.create(first_name="a", last_name="a", email="a@a.net")
        self.login(alice)
        self.assertMessage(
            self.assertGet20X("register", follow=True),
            "Registration is not set up on the website yet.",
        )

        # registration should redirect if there's no container yet
        container: RegistrationContainer = RegistrationContainerFactory.create(
            semester=semester
        )
        self.assertMessage(
            self.assertGet20X("register", follow=True),
            "This semester isn't accepting registration yet.",
        )

        # once accepting responses, the registration page should load
        container.accepting_responses = True
        container.save()
        self.assertNoMessages(self.assertGet20X("register"))

        # test reg from an old semester doesn't block registration
        old_sem = SemesterFactory.create(active=False)
        StudentRegistrationFactory.create(
            user=alice, container=RegistrationContainerFactory.create(semester=old_sem)
        )

        self.assertNoMessages(self.assertGet20X("register"))

        # make pdf
        agreement = StringIO("agree!")
        agreement.name = "agreement.pdf"

        # incorrect password
        resp = self.assertPost20X(
            "register",
            data={
                "given_name": "Alice",
                "surname": "Aardvark",
                "email_address": "myemail@example.com",
                "passcode": f"{container.passcode}1",
                "gender": "O",
                "parent_email": "myemail@example.com",
                "graduation_year": 0,
                "school_name": "Generic School District",
                "country": "USA",
                "aops_username": "",
                "agreement_form": agreement,
                "email_on_announcement": False,
                "email_on_pset_complete": True,
                "email_on_suggestion_processed": False,
                "email_on_inquiry_complete": False,
                "email_on_registration_processed": False,
            },
            follow=True,
        )
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("Wrong passcode", messages)

        # for some reason the fike variable from earlier can't be reused
        agreement2 = StringIO("agree!")
        agreement2.name = "agreement.pdf"

        # invalid post fails
        self.assertPost20X("register")

        resp = self.assertPost20X(
            "register",
            data={
                "given_name": "Alice",
                "surname": "Aardvark",
                "email_address": "myemail@example.com",
                "passcode": container.passcode,
                "gender": "O",
                "parent_email": "myemail@example.com",
                "graduation_year": 0,
                "school_name": "Generic School District",
                "country": "USA",
                "aops_username": "",
                "agreement_form": agreement2,
                "email_on_announcement": False,
                "email_on_pset_complete": True,
                "email_on_suggestion_processed": False,
                "email_on_inquiry_complete": False,
                "email_on_registration_processed": False,
            },
            follow=True,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("Submitted! Sit tight.", messages)
        self.assertTrue(StudentRegistration.objects.filter(user=alice).exists())
        alice.refresh_from_db()
        self.assertEqual(alice.first_name, "Alice")
        self.assertEqual(alice.last_name, "Aardvark")
        self.assertEqual(alice.email, "myemail@example.com")

        profile = UserProfile.objects.get(user=alice)
        self.assertFalse(profile.email_on_announcement)
        self.assertTrue(profile.email_on_pset_complete)
        self.assertFalse(profile.email_on_suggestion_processed)
        self.assertFalse(profile.email_on_inquiry_complete)
        self.assertFalse(profile.email_on_registration_processed)

        resp = self.assertPost20X(
            "register",
            data={
                "given_name": "Alice",
                "surname": "Aardvark",
                "email_address": "myemail@example.com",
                "passcode": container.passcode,
                "gender": "O",
                "parent_email": "myemail@example.com",
                "graduation_year": 0,
                "school_name": "Generic School District",
                "country": "USA",
                "aops_username": "",
                "agreement_form": agreement,
                "email_on_announcement": False,
                "email_on_pset_complete": True,
                "email_on_suggestion_processed": False,
                "email_on_inquiry_complete": False,
                "email_on_registration_processed": False,
            },
            follow=True,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(
            "You have already submitted a decision form for this year!", messages
        )

    def test_semester_switch(self) -> None:
        semester: Semester = SemesterFactory.create(
            one_semester_date=datetime.datetime(2023, 12, 25, tzinfo=UTC),
        )

        container: RegistrationContainer = RegistrationContainerFactory.create(
            semester=semester,
            accepting_responses=True,
        )
        # Suppose there are two semesters left
        with freeze_time("2023-08-01", tz_offset=0):
            StudentRegistrationFactory.create(
                container=container, user__username="alice"
            )
            StudentRegistrationFactory.create(container=container, user__username="bob")
            self.assertEqual(build_students(StudentRegistration.objects.all()), 2)
            alice: Student = Student.objects.get(user__username="alice")
            self.assertEqual(alice.invoice.total_owed, 480)
            bob: Student = Student.objects.get(user__username="bob")
            self.assertEqual(bob.invoice.total_owed, 480)

        # Now suppose the first semester has finished
        with freeze_time("2024-01-01", tz_offset=0):
            StudentRegistrationFactory.create(
                container=container, user__username="carol"
            )
            self.assertEqual(build_students(StudentRegistration.objects.all()), 1)
            carol: Student = Student.objects.get(user__username="carol")
            self.assertEqual(carol.invoice.total_owed, 240)


class AdTest(EvanTestCase):
    def test_ad_list_view_access(self) -> None:
        user = UserFactory.create()
        self.assertGet30X("ad-list")  # redirect anonymous
        self.login(user)
        self.assertGet40X("ad-list")
        verified_group, _ = Group.objects.get_or_create(name="Verified")
        user.groups.add(verified_group)
        self.assertGet20X("ad-list")

    def test_ad_list_only_shows_enabled(self) -> None:
        user = UserFactory.create()
        verified_group, _ = Group.objects.get_or_create(name="Verified")
        user.groups.add(verified_group)

        enabled_assistant: Assistant = AssistantFactory.create(
            ad_enabled=True,
            ad_url="https://example.com/enabled",
            ad_email="enabled@example.com",
            ad_blurb="I am alive.",
        )
        disabled_assistant: Assistant = AssistantFactory.create(
            ad_enabled=False,
            ad_url="https://example.com/disabled",
            ad_email="disabled@example.com",
            ad_blurb="I am not alive.",
        )

        self.login(user)
        resp = self.assertGet20X("ad-list")

        self.assertHas(resp, enabled_assistant.name)
        self.assertHas(resp, "enabled@example.com")
        self.assertHas(resp, "I am alive.")

        self.assertNotHas(resp, disabled_assistant.name)
        self.assertNotHas(resp, "disabled@example.com")
        self.assertNotHas(resp, "I am not alive.")

        self.assertNotHas(resp, "update your listing")
        self.assertNotHas(resp, "enable your entry")
        self.assertNotHas(resp, "you are not registered as an authorized instructor")

        random_staff = UserFactory.create(is_staff=True)
        random_staff.groups.add(verified_group)
        self.login(random_staff)
        resp = self.assertGet20X("ad-list")
        self.assertNotHas(resp, "update your listing")
        self.assertNotHas(resp, "enable your entry")
        self.assertHas(resp, "you are not registered as an authorized instructor")

    def test_ad_update_view_access_control(self) -> None:
        regular_user = UserFactory.create()
        assistant_user = UserFactory.create(is_staff=True)
        AssistantFactory.create(user=assistant_user)

        self.assertGet30X("ad-update")  # anonymous redirects to login

        self.login(regular_user)
        self.assertGet40X("ad-update")

        self.login(assistant_user)
        self.assertGet20X("ad-update")

    def test_ad_update(self) -> None:
        assistant_user = UserFactory.create(is_staff=True)
        assistant: Assistant = AssistantFactory.create(
            user=assistant_user,
            ad_enabled=False,
            ad_url="",
            ad_email="",
            ad_blurb="",
        )

        self.login(assistant_user)
        verified_group, _ = Group.objects.get_or_create(name="Verified")
        assistant_user.groups.add(verified_group)
        resp = self.assertGet20X("ad-list")
        self.assertHas(resp, "enable your entry")

        self.assertGet20X("ad-update")
        resp = self.assertPost20X(
            "ad-update",
            data={
                "ad_enabled": True,
                "ad_url": "https://evanchen.cc/",
                "ad_email": "overlord@evanchen.cc",
                "ad_blurb": "I'm an ovie!",
            },
            follow=True,
        )
        messages = [m.message for m in resp.context["messages"]]
        self.assertIn("Updated successfully.", messages)

        assistant.refresh_from_db()
        self.assertTrue(assistant.ad_enabled)
        self.assertEqual(assistant.ad_url, "https://evanchen.cc/")
        self.assertEqual(assistant.ad_email, "overlord@evanchen.cc")
        self.assertEqual(assistant.ad_blurb, "I'm an ovie!")

        resp = self.assertGet20X("ad-list")
        self.assertHas(resp, "update your listing below")

    def test_ad_update_unauthorized_assistant(self) -> None:
        assistant1_user = UserFactory.create(is_staff=True)
        assistant2_user = UserFactory.create(is_staff=True)
        assistant1: Assistant = AssistantFactory.create(user=assistant1_user)
        assistant2: Assistant = AssistantFactory.create(user=assistant2_user)

        self.login(assistant1_user)
        resp = self.get("ad-update")
        self.assertEqual(resp.context["assistant"], assistant1)

        self.login(assistant2_user)
        resp = self.get("ad-update")
        self.assertEqual(resp.context["assistant"], assistant2)

    def test_ad_list_edit_link_visibility(self) -> None:
        assistant_user = UserFactory.create(is_staff=True)
        other_user = UserFactory.create()

        verified_group, _ = Group.objects.get_or_create(name="Verified")
        assistant_user.groups.add(verified_group)
        other_user.groups.add(verified_group)

        AssistantFactory.create(user=assistant_user, ad_enabled=True)

        self.login(assistant_user)
        resp = self.assertGet20X("ad-list")
        self.assertHas(resp, "(edit)")

        self.login(other_user)
        resp = self.assertGet20X("ad-list")
        self.assertNotHas(resp, "(edit)")
