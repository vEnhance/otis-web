import datetime
from io import StringIO

import pytest
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
from roster.factories import (
    ApplyUUIDFactory,
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


@pytest.mark.django_db
def test_username_lookup(otis) -> None:
    admin: User = UserFactory.create(is_superuser=True, is_staff=True)
    semester_old: Semester = SemesterFactory.create(end_year=2025)
    semester_new: Semester = SemesterFactory.create(end_year=2026)
    bob: User = UserFactory.create(username="bob")
    StudentFactory.create(user=bob, semester=semester_old)
    bob_new: Student = StudentFactory.create(user=bob, semester=semester_new)

    otis.login(admin)
    otis.get_not_found("username-lookup", "carl")

    resp = otis.get("username-lookup", "bob")
    assert resp.url == bob_new.get_absolute_url()


@pytest.mark.django_db
def test_email_lookup(otis) -> None:
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
    otis.get_30x("email-lookup")

    # Test access control - regular user should be denied
    otis.login(regular_user)
    otis.get_40x("email-lookup")

    # Test GET request with admin user - should show form
    otis.login(admin)
    resp = otis.get_20x("email-lookup")
    otis.assert_has(resp, "Email lookup")

    # Test POST with valid email that matches a student (should redirect)
    resp = otis.post("email-lookup", data={"email": "alice@example.com"})
    assert resp.url == alice_new.get_absolute_url()

    # Test POST with valid email but no matching student (should show warning)
    resp = otis.post_20x(
        "email-lookup", data={"email": "nonexistent@example.com"}, follow=True
    )
    messages = [m.message for m in resp.context["messages"]]
    assert "No matches found" in messages

    # Test POST with invalid email format (form validation should catch it)
    resp = otis.post_20x(
        "email-lookup",
        data={"email": "invalid_email"},
    )
    # Form should be re-displayed with errors, no redirect should occur
    otis.assert_has(resp, "Email lookup")

    # Test case insensitive matching
    resp = otis.post("email-lookup", data={"email": "BOB@EXAMPLE.COM"})
    assert resp.url == bob_student.get_absolute_url()


@pytest.mark.django_db
def test_update_profile(otis) -> None:
    alice: User = UserFactory.create()
    otis.login(alice)

    otis.get_20x("update-profile")

    first_name = alice.first_name
    last_name = alice.last_name
    email = alice.email

    invalid_resp = otis.post_20x(
        "update-profile",
        data={
            "first_name": f"a{first_name}",
            "last_name": f"a{last_name}",
            "email": "invalid_Email!!",
        },
    )

    messages = [m.message for m in invalid_resp.context["messages"]]
    assert "Your information has been updated." not in messages

    same_email_resp = otis.post_20x(
        "update-profile",
        data={
            "first_name": f"a{first_name}",
            "last_name": f"a{last_name}",
            "email": email,
        },
    )

    messages = [m.message for m in same_email_resp.context["messages"]]
    assert "Your information has been updated." in messages

    resp = otis.post_20x(
        "update-profile",
        data={
            "first_name": f"a{first_name}",
            "last_name": f"a{last_name}",
            "email": f"1{email}",
        },
    )

    messages = [m.message for m in resp.context["messages"]]
    assert "Your information has been updated." in messages

    alice.refresh_from_db()
    assert f"a{first_name}" == alice.first_name
    assert f"a{last_name}" == alice.last_name
    assert f"1{email}" == alice.email


@pytest.mark.django_db
def test_mystery(otis) -> None:
    mysteryGroup: UnitGroup = UnitGroupFactory.create(name="Mystery")
    mystery: Unit = UnitFactory(group=mysteryGroup)  # type: ignore
    added_unit: Unit = UnitFactory.create_batch(2)[1]  # next two units

    alice: Student = StudentFactory.create()
    otis.login(alice)

    otis.assert_response_denied(
        otis.client.get("/roster/mystery-unlock/easier/", follow=True)
    )

    alice.curriculum.set([mystery])
    alice.unlocked_units.set([mystery])

    resp = otis.client.get("/roster/mystery-unlock/harder/", follow=True)
    otis.assert_response_20x(resp)

    assert not alice.curriculum.contains(mystery)
    assert not alice.unlocked_units.contains(mystery)

    assert alice.curriculum.contains(added_unit)
    assert alice.unlocked_units.contains(added_unit)

    messages = [m.message for m in resp.context["messages"]]
    assert f"Added the unit {added_unit}" in messages


@pytest.mark.django_db
def test_giga_chart(otis) -> None:
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
    otis.login(admin)
    otis.get_20x("giga-chart", "csv", follow=True)

    resp = otis.get_20x("giga-chart", "html", follow=True)
    for student in students:
        for prop in [
            student.name,
            student.user.email,
            student.reg.parent_email,
        ]:
            otis.assert_has(resp, prop)


@pytest.mark.django_db
def test_student_assistant_list(otis) -> None:
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
    otis.login(staff)
    resp = otis.get_20x("instructors")
    for i in range(1, 6):
        otis.assert_has(resp, f'"F{i} L{i}"')
        otis.assert_has(resp, f"user{i}@evanchen.cc")
    otis.assert_has(resp, "GoodKid", count=2 * (1 + 4 + 9 + 16 + 25))
    otis.assert_has(resp, r"&lt;user5@evanchen.cc&gt;")
    otis.assert_not_has(resp, "BadKid")
    otis.assert_not_has(resp, "out of sync")  # only admins can see the sync button

    admin: User = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)
    resp = otis.get_20x("instructors")
    otis.assert_has(resp, "out of sync")

    group = Group.objects.get(name="Active Staff")
    qs: QuerySet[User] = group.user_set.all()  # type: ignore
    assert qs.count() == 0

    resp = otis.post_ok("instructors")
    assert qs.count() == 5
    otis.assert_not_has(resp, "out of sync")
    resp = otis.get_ok("instructors")
    otis.assert_not_has(resp, "out of sync")

    otis.login(staff)
    otis.post_40x("instructors")  # staff can't post


@pytest.mark.django_db
def test_advance(otis) -> None:
    assist: Assistant = AssistantFactory.create()
    alice: Student = StudentFactory.create(assistant=assist)

    otis.login(alice)

    otis.get_denied("advance", alice.pk)

    units: list[Unit] = UnitFactory.create_batch(4)

    # unlock 0, add 1, lock 2, drop 3

    alice.curriculum.set(units[2:4])  # units 3 and 4
    alice.unlocked_units.set([units[3]])

    otis.login(assist)

    otis.get_20x("advance", alice.pk)

    invalid_resp = otis.post_20x(
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
    assert "Successfully updated student." not in messages

    resp = otis.post_20x(
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
    assert "Successfully updated student." in messages

    alice.refresh_from_db()
    assert alice.unlocked_units.contains(units[0])
    assert not alice.unlocked_units.contains(units[1])
    assert not alice.unlocked_units.contains(units[3])

    assert alice.curriculum.contains(units[0])
    assert alice.curriculum.contains(units[1])
    assert not alice.unlocked_units.contains(units[2])
    assert alice.curriculum.contains(units[2])
    assert not alice.curriculum.contains(units[3])


@pytest.mark.django_db
def test_link_assistant(otis) -> None:
    assistant = AssistantFactory.create()
    assistant2 = AssistantFactory.create()
    alice = StudentFactory.create()
    StudentFactory.create()
    StudentFactory.create(assistant=assistant)
    StudentFactory.create(assistant=assistant2)

    otis.get_30x("link-assistant")  # anonymous redirects to login
    otis.login(UserFactory.create(is_staff=False))
    otis.get_40x("link-assistant")

    otis.login(assistant.user)
    resp = otis.get_ok("link-assistant")
    assert len(resp.context["form"].fields["student"].queryset) == 2
    otis.post_ok("link-assistant", data={"student": alice.pk})
    alice.refresh_from_db()
    assert alice.assistant.pk == assistant.pk
    resp = otis.get_ok("link-assistant")
    assert len(resp.context["form"].fields["student"].queryset) == 1


@pytest.mark.django_db
def test_curriculum(otis) -> None:
    staff: Assistant = AssistantFactory.create()
    alice: Student = StudentFactory.create(assistant=staff)

    unitgroups: list[UnitGroup] = UnitGroupFactory.create_batch(4)
    for unitgroup in unitgroups:
        for letter in "BDZ":
            UnitFactory.create(
                code=letter + unitgroup.subject[0] + "W", group=unitgroup
            )

    otis.login(alice)
    otis.assert_has(otis.get("currshow", alice.pk), text="you are not an instructor")

    otis.login(staff)
    otis.assert_not_has(
        otis.get("currshow", alice.pk), text="you are not an instructor"
    )

    invalid_data = {
        "group-0": [
            "invalid",
        ],
        "group-1": [4, 6],
        "group-3": [10, 11, 12],
    }
    resp = otis.post("currshow", alice.pk, data=invalid_data)
    assert len(get_object_or_404(Student, pk=alice.pk).curriculum.all()) != 6

    messages = [m.message for m in resp.context["messages"]]
    assert "Successfully saved curriculum of 6 units." not in messages

    data = {
        "group-0": [
            1,
        ],
        "group-1": [4, 6],
        "group-3": [10, 11, 12],
    }
    resp = otis.post("currshow", alice.pk, data=data)
    assert len(get_object_or_404(Student, pk=alice.pk).curriculum.all()) == 6

    messages = [m.message for m in resp.context["messages"]]
    assert "Successfully saved curriculum of 6 units." in messages


@pytest.mark.django_db
def test_finalize(otis) -> None:
    alice: Student = StudentFactory.create(newborn=True)
    otis.login(alice)
    otis.assert_has(
        otis.post("finalize", alice.pk, data={"submit": True}, follow=True),
        "You should select some units",
    )
    units: list[Unit] = UnitFactory.create_batch(20)
    alice.curriculum.set(units)
    otis.assert_has(
        otis.post("finalize", alice.pk, data={}, follow=True),
        "Your curriculum has been finalized!",
    )
    assert alice.unlocked_units.count() == 3
    otis.post_40x("finalize", alice.pk, data={"submit": True})


@pytest.mark.django_db
def test_student_properties(otis) -> None:
    alice: Student = StudentFactory.create()
    units: list[Unit] = UnitFactory.create_batch(10)
    alice.curriculum.set(units[:7])
    alice.unlocked_units.set(units[2:5])
    assert alice.curriculum_length == 7
    assert alice.num_unlocked == 3


@pytest.mark.django_db
def test_master_schedule(otis) -> None:
    alice: Student = StudentFactory.create(
        user__first_name="Ada", user__last_name="Adalhaidis"
    )
    units: list[Unit] = UnitFactory.create_batch(10)
    alice.curriculum.set(units[:8])
    otis.login(UserFactory.create(is_staff=True))
    otis.assert_has(
        otis.get("master-schedule"),
        text=f'title="{alice.user.first_name} {alice.user.last_name}"',
        count=8,
    )


@pytest.mark.django_db
def test_inquiry(otis) -> None:
    firefly: Assistant = AssistantFactory.create()
    alice: Student = StudentFactory.create(assistant=firefly)
    units: list[Unit] = UnitFactory.create_batch(20)
    otis.login(alice)

    # Check that an invalid unit is not processed
    invalid_resp = otis.post(
        "inquiry",
        alice.pk,
        data={
            "unit": "invalid",
            "action_type": "INQ_ACT_UNLOCK",
            "explanation": "hi",
        },
    )
    otis.assert_not_has(invalid_resp, "Petition automatically processed")

    with freeze_time("2025-10-29", tz_offset=0):
        # Alice unlocks 6 units, should be autoprocessed.
        for i in range(6):
            resp = otis.post(
                "inquiry",
                alice.pk,
                data={
                    "unit": units[i].pk,
                    "action_type": "INQ_ACT_UNLOCK",
                    "explanation": "hi",
                },
                follow=True,
            )
            otis.assert_has(resp, "Petition automatically processed")
            inq = UnitInquiry.objects.get(
                student=alice, unit=units[i].pk, action_type="INQ_ACT_UNLOCK"
            )
            assert inq.was_auto_processed
            assert inq.status == "INQ_ACC"

        otis.get_20x("inquiry", alice.pk, follow=True)

        # Now Alice has done 6 units, they shouldn't be able to get more
        # (This differs from production behavior because production also gives you a default three units)
        assert alice.curriculum.count() == 6
        assert alice.unlocked_units.count() == 6
        otis.assert_has(
            otis.post(
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
        assert not inq.was_auto_processed
        assert inq.status == "INQ_NEW"

        assert alice.curriculum.count() == 6
        assert alice.unlocked_units.count() == 6

        # We have our assistant lock a unit
        otis.login(firefly)
        otis.assert_has(
            otis.post(
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
        assert alice.curriculum.count() == 6
        assert alice.unlocked_units.count() == 5
        inq = UnitInquiry.objects.get(
            student=alice, unit=units[3].pk, action_type="INQ_ACT_LOCK"
        )
        assert inq.was_auto_processed
        assert inq.status == "INQ_ACC"
        assert not alice.unlocked_units.contains(units[3])

        # Now dropping should be autoprocessed by Alice
        otis.login(alice)
        otis.assert_has(
            otis.post(
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
        assert inq.was_auto_processed
        assert inq.status == "INQ_ACC"

        assert alice.curriculum.count() == 5
        assert alice.unlocked_units.count() == 5

    with freeze_time("2025-10-30", tz_offset=0):
        # We now give Alice some more units :o
        otis.login(firefly)
        for i in range(6, 10):
            otis.assert_has(
                otis.post(
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
            assert inq.was_auto_processed
            assert inq.status == "INQ_ACC"
        assert alice.curriculum.count() == 9
        assert alice.unlocked_units.count() == 9

        # Check that you can't unlock more units when you are already at nine
        otis.login(alice)
        for i in range(11, 14):
            otis.assert_has(
                otis.post(
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
            assert inq.was_auto_processed
            assert inq.status == "INQ_REJ"
        assert alice.curriculum.count() == 9
        assert alice.unlocked_units.count() == 9

        # appending should be autoprocessed
        for i in range(15, 18):
            otis.assert_has(
                otis.post(
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
            assert inq.was_auto_processed
            assert inq.status == "INQ_ACC"
        assert alice.curriculum.count() == 12
        assert alice.unlocked_units.count() == 9

        # check that petitions are now locked because of abnormally large count
        otis.assert_has(
            otis.post(
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
        assert not inq.was_auto_processed
        assert inq.status == "INQ_HOLD"

        # drop a bunch of units for alice
        otis.login(firefly)
        for i in range(4, 14):
            otis.assert_has(
                otis.post(
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
            assert inq.was_auto_processed
            assert inq.status == "INQ_ACC"
        assert alice.curriculum.count() == 6
        assert alice.unlocked_units.count() == 3

    with freeze_time("2025-10-31", tz_offset=0):
        otis.assert_has(
            otis.post(
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
        assert alice.curriculum.count() == 7
        assert alice.unlocked_units.count() == 4
        inq = UnitInquiry.objects.get(
            student=alice,
            unit=units[5].pk,
            action_type="INQ_ACT_UNLOCK",
            explanation="add back in",
        )
        assert inq.was_auto_processed
        assert inq.status == "INQ_ACC"

        # Alice hit the hold limit earlier, this just circumvents it.
        otis.login(alice)
        PSetFactory.create_batch(30, student=alice)
        alice.save()

        # secret unit should be autoprocessed!
        secret_group = UnitGroupFactory.create(
            name="Spooky Unit", subject="K", hidden=True
        )
        secret_unit = UnitFactory.create(code="BKV", group=secret_group)
        alice.curriculum.add(secret_unit)

        otis.assert_has(
            otis.post(
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
        assert alice.curriculum.count() == 8
        assert alice.unlocked_units.count() == 5
        inq = UnitInquiry.objects.get(
            student=alice, unit=secret_unit.pk, action_type="INQ_ACT_UNLOCK"
        )
        assert inq.was_auto_processed
        assert inq.status == "INQ_ACC"

        # check that autoprocessing old units works
        inactive_semester = SemesterFactory.create(active=False)
        inactive_alice = StudentFactory.create(
            semester=inactive_semester, user=alice.user
        )
        old_group = UnitGroupFactory.create(name="Last Year Unit", subject="A")
        old_unit = UnitFactory.create(code="BAW", group=old_group)
        inactive_alice.curriculum.add(old_unit)
        inactive_alice.unlocked_units.add(old_unit)
        assert inactive_alice.curriculum.count() == 1
        assert inactive_alice.unlocked_units.count() == 1
        inactive_alice.save()
        otis.assert_has(
            otis.post(
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
        assert inq.was_auto_processed
        assert inq.status == "INQ_ACC"
        assert alice.curriculum.count() == 9
        assert alice.unlocked_units.count() == 6

    # test a bunch of fail conditions
    bob: Student = StudentFactory.create(
        semester=SemesterFactory.create(active=False)
    )
    otis.login(bob)
    otis.get_denied("inquiry", bob.pk)

    carl: Student = StudentFactory.create(enabled=False)
    otis.login(carl)
    otis.get_denied("inquiry", carl.pk)

    dave: Student = StudentFactory.create(newborn=True)
    otis.login(dave)
    otis.get_denied("inquiry", dave.pk)

    invoice_semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2021, 7, 1, tzinfo=UTC),
    )
    eve = StudentFactory.create(semester=invoice_semester)
    otis.login(eve)
    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=eve)

    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("inquiry", eve.pk)


@pytest.mark.django_db
def test_inquiry_cant_rapid_fire(otis) -> None:
    with freeze_time("2025-10-31", tz_offset=0):
        alice = StudentFactory.create()
        unit = UnitFactory.create()
        otis.login(alice)
        otis.assert_has(
            otis.post(
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
        otis.assert_has(
            otis.post(
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


@pytest.mark.django_db
def test_cancel_inquiry_sets_status_to_canceled(otis) -> None:
    alice = StudentFactory.create()
    unit = UnitFactory.create()
    inquiry = UnitInquiry.objects.create(
        student=alice,
        unit=unit,
        action_type="INQ_ACT_UNLOCK",
        status="INQ_NEW",
        explanation="Please unlock",
    )
    otis.login(alice)
    resp = otis.post_20x(
        "inquiry-cancel",
        inquiry.pk,
        follow=True,
    )
    inquiry.refresh_from_db()
    assert inquiry.status == "INQ_CANC"
    otis.assert_has(resp, "Inquiry successfully canceled.")


@pytest.mark.django_db
def test_only_owner_or_staff_can_cancel(otis):
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
    otis.login(bob)
    otis.post_40x("inquiry-cancel", inquiry.pk)
    inquiry.refresh_from_db()
    assert inquiry.status == "INQ_NEW"  # Ensure status is still "INQ_NEW"

    # Staff can cancel
    otis.login(staff)
    otis.post_20x("inquiry-cancel", inquiry.pk, follow=True)
    inquiry.refresh_from_db()
    assert inquiry.status == "INQ_CANC"


@pytest.mark.django_db
def test_cancel_button_only_for_pending(otis):
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
        otis.login(alice)
        otis.get_20x("inquiry", alice.pk)


@pytest.mark.django_db
def test_cannot_cancel_non_pending(otis):
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
        otis.login(alice)
        otis.post_40x("inquiry-cancel", inquiry.pk)
        inquiry.refresh_from_db()
        assert inquiry.status == status


@pytest.mark.django_db
def test_invoice(otis) -> None:
    alice: Student = StudentFactory.create(semester__show_invoices=True)
    otis.login(alice)
    InvoiceFactory.create(
        student=alice,
        preps_taught=2,
        hours_taught=8.4,
        adjustment=-30,
        credits=70,
        extras=100,
        total_paid=400,
    )
    response = otis.get("invoice", follow=True)
    otis.assert_has(response, "752.00")
    checksum = alice.get_checksum(settings.INVOICE_HASH_KEY)
    assert len(checksum) == 36
    otis.assert_has(response, checksum)


@pytest.mark.django_db
def test_delinquency(otis) -> None:
    semester: Semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2022, 9, 21, tzinfo=UTC),
        most_payment_deadline=datetime.datetime(2023, 1, 21, tzinfo=UTC),
    )

    alice: Student = StudentFactory.create(semester=semester)

    assert alice.payment_status == 0  # because no invoice exists
    with freeze_time("2022-08-05", tz_offset=0):
        invoice: Invoice = InvoiceFactory.create(
            student=alice,
            preps_taught=2,
        )

    # Alice has paid $0 so far
    assert invoice.total_owed == 480
    with freeze_time("2022-09-05", tz_offset=0):
        assert alice.payment_status == 4
        assert not alice.is_delinquent
    with freeze_time("2022-09-17", tz_offset=0):
        assert alice.payment_status == 1
        assert not alice.is_delinquent
    with freeze_time("2022-09-25", tz_offset=0):
        assert alice.payment_status == 2
        assert not alice.is_delinquent
    with freeze_time("2022-10-15", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
        invoice.forgive_date = datetime.datetime(2022, 10, 31, tzinfo=UTC)
        invoice.save()
        assert not alice.is_delinquent
    with freeze_time("2022-11-15", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
    # Now suppose Alice makes the first payment
    invoice.total_paid = 240
    invoice.save()
    assert invoice.total_owed == 240
    with freeze_time("2022-09-05", tz_offset=0):
        assert alice.payment_status == 4
        assert not alice.is_delinquent
    with freeze_time("2022-09-17", tz_offset=0):
        assert alice.payment_status == 4
        assert not alice.is_delinquent
    with freeze_time("2022-09-25", tz_offset=0):
        assert alice.payment_status == 4
        assert not alice.is_delinquent
    with freeze_time("2022-10-15", tz_offset=0):
        assert alice.payment_status == 4
        assert not alice.is_delinquent
    with freeze_time("2023-01-17", tz_offset=0):
        assert alice.payment_status == 5
        assert not alice.is_delinquent
    with freeze_time("2023-01-25", tz_offset=0):
        assert alice.payment_status == 6
        assert not alice.is_delinquent
    with freeze_time("2023-02-15", tz_offset=0):
        assert alice.payment_status == 7
        assert alice.is_delinquent
        invoice.forgive_date = datetime.datetime(2023, 2, 28, tzinfo=UTC)
        invoice.save()
        assert not alice.is_delinquent
    with freeze_time("2023-06-05", tz_offset=0):
        assert alice.payment_status == 7
        assert alice.is_delinquent
    # Now suppose Alice makes the last payment
    invoice.total_paid = 480
    invoice.save()
    assert invoice.total_owed == 0
    with freeze_time("2023-02-15", tz_offset=0):
        assert alice.payment_status == 0
        assert not alice.is_delinquent

    bob: Student = StudentFactory.create(semester=semester)

    # Bob gets a bit of extra time to pay because he joined recently
    with freeze_time("2023-1-23", tz_offset=0):
        invoice2: Invoice = InvoiceFactory.create(
            student=bob,
            preps_taught=1,
        )
        assert bob.payment_status == 1
        assert not bob.is_delinquent

    # Now he is affected
    semester.first_payment_deadline = datetime.datetime(2023, 1, 28, tzinfo=UTC)
    semester.save()

    with freeze_time("2023-2-08", tz_offset=0):
        assert bob.payment_status == 3
        assert bob.is_delinquent

    invoice2.total_paid = 120
    invoice2.save()

    with freeze_time("2023-2-08", tz_offset=0):
        assert bob.payment_status == 7
        assert bob.is_delinquent

    semester.most_payment_deadline = datetime.datetime(2023, 2, 21, tzinfo=UTC)
    semester.save()

    with freeze_time("2023-3-01", tz_offset=0):
        assert bob.payment_status == 7
        assert bob.is_delinquent


@pytest.mark.django_db
def test_delinquency_for_joining_second_semester(otis) -> None:
    semester: Semester = SemesterFactory.create(
        show_invoices=True,
        first_payment_deadline=datetime.datetime(2022, 9, 21, tzinfo=UTC),
        most_payment_deadline=datetime.datetime(2023, 1, 21, tzinfo=UTC),
        one_semester_date=datetime.datetime(2022, 12, 30, tzinfo=UTC),
    )

    alice: Student = StudentFactory.create(semester=semester)
    bob: Student = StudentFactory.create(semester=semester)
    assert alice.payment_status == 0  # because no invoice exists
    assert bob.payment_status == 0  # because no invoice exists
    with freeze_time("2022-08-05", tz_offset=0):
        InvoiceFactory.create(student=alice, preps_taught=2)
    with freeze_time("2023-01-01", tz_offset=0):
        InvoiceFactory.create(student=bob, preps_taught=1)

    with freeze_time("2023-01-02", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
        assert bob.payment_status == 4
        assert not bob.is_delinquent

    with freeze_time("2023-01-20", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
        assert bob.payment_status == 1
        assert not bob.is_delinquent

    with freeze_time("2023-01-25", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
        assert bob.payment_status == 2
        assert not bob.is_delinquent

    with freeze_time("2023-01-30", tz_offset=0):
        assert alice.payment_status == 3
        assert alice.is_delinquent
        assert bob.payment_status == 3
        assert bob.is_delinquent


@pytest.mark.django_db
def test_update_invoice(otis) -> None:
    firefly: Assistant = AssistantFactory.create()
    alice: Student = StudentFactory.create(assistant=firefly)
    invoice: Invoice = InvoiceFactory.create(student=alice)
    otis.login(firefly)
    otis.get_20x("edit-invoice", alice.pk)
    otis.post_redirects(
        otis.url("invoice", invoice.pk),
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


@pytest.mark.django_db
def test_reg(otis) -> None:
    semester: Semester = SemesterFactory.create()

    # registration should redirect if there's no container yet
    alice: User = UserFactory.create(first_name="a", last_name="a", email="a@a.net")
    otis.login(alice)
    otis.assert_message(
        otis.get_20x("register", follow=True),
        "Registration is not set up on the website yet.",
    )

    # registration should redirect if there's no container yet
    container: RegistrationContainer = RegistrationContainerFactory.create(
        semester=semester
    )
    otis.assert_message(
        otis.get_20x("register", follow=True),
        "This semester isn't accepting registration yet.",
    )

    # once accepting responses, the registration page should load
    container.accepting_responses = True
    container.save()
    otis.assert_no_messages(otis.get_20x("register"))

    # test reg from an old semester doesn't block registration
    old_sem = SemesterFactory.create(active=False)
    StudentRegistrationFactory.create(
        user=alice, container=RegistrationContainerFactory.create(semester=old_sem)
    )

    otis.assert_no_messages(otis.get_20x("register"))

    # make pdf
    agreement = StringIO("agree!")
    agreement.name = "agreement.pdf"

    # incorrect password
    resp = otis.post_20x(
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
    assert "Wrong passcode" in messages

    # for some reason the fake variable from earlier can't be reused
    agreement2 = StringIO("agree!")
    agreement2.name = "agreement.pdf"

    # invalid post fails
    otis.post_20x("register")

    resp = otis.post_20x(
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
    assert "Submitted! Sit tight." in messages
    assert StudentRegistration.objects.filter(user=alice).exists()
    alice.refresh_from_db()
    assert alice.first_name == "Alice"
    assert alice.last_name == "Aardvark"
    assert alice.email == "myemail@example.com"

    profile = UserProfile.objects.get(user=alice)
    assert not profile.email_on_announcement
    assert profile.email_on_pset_complete
    assert not profile.email_on_suggestion_processed
    assert not profile.email_on_inquiry_complete
    assert not profile.email_on_registration_processed

    resp = otis.post_20x(
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
    assert "You have already submitted a decision form for this year!" in messages


@pytest.mark.django_db
def test_semester_switch(otis) -> None:
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
        assert build_students(StudentRegistration.objects.all()) == 2
        alice: Student = Student.objects.get(user__username="alice")
        assert alice.invoice.total_owed == 480
        bob: Student = Student.objects.get(user__username="bob")
        assert bob.invoice.total_owed == 480

    # Now suppose the first semester has finished
    with freeze_time("2024-01-01", tz_offset=0):
        StudentRegistrationFactory.create(
            container=container, user__username="carol"
        )
        assert build_students(StudentRegistration.objects.all()) == 1
        carol: Student = Student.objects.get(user__username="carol")
        assert carol.invoice.total_owed == 240


@pytest.mark.django_db
def test_reg_with_apply_uuid(otis) -> None:
    au = ApplyUUIDFactory.create(percent_aid=70)
    semester: Semester = SemesterFactory.create()

    # registration should redirect if there's no container yet
    alice: User = UserFactory.create(first_name="a", last_name="a", email="a@a.net")
    otis.login(alice)
    # registration should redirect if there's no container yet
    container: RegistrationContainer = RegistrationContainerFactory.create(
        semester=semester, accepting_responses=True
    )
    # make pdf
    agreement = StringIO("i do!")
    agreement.name = "agreement.pdf"

    # incorrect password
    resp = otis.post_20x(
        "register",
        data={
            "given_name": "Alice",
            "surname": "Aardvark",
            "email_address": "myemail@example.com",
            "passcode": "MEOW",
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
    assert "Wrong passcode" in messages

    # for some reason the fake variable from earlier can't be reused
    agreement2 = StringIO("i do too!")
    agreement2.name = "agreement.pdf"

    # invalid post fails
    otis.post_20x("register")

    resp = otis.post_20x(
        "register",
        data={
            "given_name": "Alice",
            "surname": "Aardvark",
            "email_address": "myemail@example.com",
            "passcode": au.uuid,
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
    assert "Submitted! Sit tight." in messages
    alice_reg = StudentRegistration.objects.get(user=alice)
    alice.refresh_from_db()
    assert alice.first_name == "Alice"
    assert alice.last_name == "Aardvark"
    assert alice.email == "myemail@example.com"
    au.refresh_from_db()
    assert au.reg == alice_reg

    # Bob shouldn't be able to steal Alice's passcode
    bob: User = UserFactory.create(
        first_name="Bob", last_name="Beta", email="b@b.net"
    )
    otis.login(bob)

    agreement3 = StringIO("i do three!")
    agreement3.name = "agreement.pdf"
    otis.post_40x(
        "register",
        data={
            "given_name": "Bob",
            "surname": "Beta",
            "email_address": "bob@example.com",
            "passcode": au.uuid,
            "gender": "O",
            "parent_email": "bob@example.com",
            "graduation_year": 0,
            "school_name": "Generic School District",
            "country": "USA",
            "aops_username": "",
            "agreement_form": agreement3,
            "email_on_announcement": False,
            "email_on_pset_complete": True,
            "email_on_suggestion_processed": False,
            "email_on_inquiry_complete": False,
            "email_on_registration_processed": False,
        },
        follow=True,
    )

    agreement4 = StringIO("i do four!")
    agreement4.name = "agreement.pdf"
    # Let's generate an ApplyUUID for Bob too
    au2 = ApplyUUIDFactory.create(percent_aid=0)
    otis.post_20x(
        "register",
        data={
            "given_name": "Bob",
            "surname": "Beta",
            "email_address": "bob@example.com",
            "passcode": au2.uuid,
            "gender": "O",
            "parent_email": "bob@example.com",
            "graduation_year": 0,
            "school_name": "Generic School District",
            "country": "USA",
            "aops_username": "",
            "agreement_form": agreement4,
            "email_on_announcement": False,
            "email_on_pset_complete": True,
            "email_on_suggestion_processed": False,
            "email_on_inquiry_complete": False,
            "email_on_registration_processed": False,
        },
        follow=True,
    )

    # Meanwhile, Carol just registers by passcode
    agreement5 = StringIO("i do five!")
    agreement5.name = "agreement.pdf"
    carol: User = UserFactory.create(
        first_name="Carol", last_name="Cutie", email="c@c.net"
    )
    otis.login(carol)
    otis.post_20x(
        "register",
        data={
            "given_name": "Carol",
            "surname": "Cutie",
            "email_address": "carol@example.com",
            "passcode": container.passcode,
            "gender": "O",
            "parent_email": "carol@example.com",
            "graduation_year": 0,
            "school_name": "Generic School District",
            "country": "USA",
            "aops_username": "",
            "agreement_form": agreement5,
            "email_on_announcement": False,
            "email_on_pset_complete": True,
            "email_on_suggestion_processed": False,
            "email_on_inquiry_complete": False,
            "email_on_registration_processed": False,
        },
        follow=True,
    )

    build_students(StudentRegistration.objects.all())
    assert Invoice.objects.get(student__user=alice).total_owed == 144
    assert Invoice.objects.get(student__user=bob).total_owed == 480


@pytest.mark.django_db
def test_ad_list_view_access(otis) -> None:
    user = UserFactory.create()
    otis.get_30x("ad-list")  # redirect anonymous
    otis.login(user)
    otis.get_40x("ad-list")
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user.groups.add(verified_group)
    otis.get_20x("ad-list")


@pytest.mark.django_db
def test_ad_list_only_shows_enabled(otis) -> None:
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

    otis.login(user)
    resp = otis.get_20x("ad-list")

    otis.assert_has(resp, enabled_assistant.name)
    otis.assert_has(resp, "enabled@example.com")
    otis.assert_has(resp, "I am alive.")

    otis.assert_not_has(resp, disabled_assistant.name)
    otis.assert_not_has(resp, "disabled@example.com")
    otis.assert_not_has(resp, "I am not alive.")

    otis.assert_not_has(resp, "update your listing")
    otis.assert_not_has(resp, "enable your entry")
    otis.assert_not_has(resp, "you are not registered as an authorized instructor")

    random_staff = UserFactory.create(is_staff=True)
    random_staff.groups.add(verified_group)
    otis.login(random_staff)
    resp = otis.get_20x("ad-list")
    otis.assert_not_has(resp, "update your listing")
    otis.assert_not_has(resp, "enable your entry")
    otis.assert_has(resp, "you are not registered as an authorized instructor")


@pytest.mark.django_db
def test_ad_update_view_access_control(otis) -> None:
    regular_user = UserFactory.create()
    assistant_user = UserFactory.create(is_staff=True)
    AssistantFactory.create(user=assistant_user)

    otis.get_30x("ad-update")  # anonymous redirects to login

    otis.login(regular_user)
    otis.get_40x("ad-update")

    otis.login(assistant_user)
    otis.get_20x("ad-update")


@pytest.mark.django_db
def test_ad_update(otis) -> None:
    assistant_user = UserFactory.create(is_staff=True)
    assistant: Assistant = AssistantFactory.create(
        user=assistant_user,
        ad_enabled=False,
        ad_url="",
        ad_email="",
        ad_blurb="",
    )

    otis.login(assistant_user)
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    assistant_user.groups.add(verified_group)
    resp = otis.get_20x("ad-list")
    otis.assert_has(resp, "enable your entry")

    otis.get_20x("ad-update")
    resp = otis.post_20x(
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
    assert "Updated successfully." in messages

    assistant.refresh_from_db()
    assert assistant.ad_enabled
    assert assistant.ad_url == "https://evanchen.cc/"
    assert assistant.ad_email == "overlord@evanchen.cc"
    assert assistant.ad_blurb == "I'm an ovie!"

    resp = otis.get_20x("ad-list")
    otis.assert_has(resp, "update your listing below")


@pytest.mark.django_db
def test_ad_update_unauthorized_assistant(otis) -> None:
    assistant1_user = UserFactory.create(is_staff=True)
    assistant2_user = UserFactory.create(is_staff=True)
    assistant1: Assistant = AssistantFactory.create(user=assistant1_user)
    assistant2: Assistant = AssistantFactory.create(user=assistant2_user)

    otis.login(assistant1_user)
    resp = otis.get("ad-update")
    assert resp.context["assistant"] == assistant1

    otis.login(assistant2_user)
    resp = otis.get("ad-update")
    assert resp.context["assistant"] == assistant2


@pytest.mark.django_db
def test_ad_list_edit_link_visibility(otis) -> None:
    assistant_user = UserFactory.create(is_staff=True)
    other_user = UserFactory.create()

    verified_group, _ = Group.objects.get_or_create(name="Verified")
    assistant_user.groups.add(verified_group)
    other_user.groups.add(verified_group)

    AssistantFactory.create(user=assistant_user, ad_enabled=True)

    otis.login(assistant_user)
    resp = otis.get_20x("ad-list")
    otis.assert_has(resp, "(edit)")

    otis.login(other_user)
    resp = otis.get_20x("ad-list")
    otis.assert_not_has(resp, "(edit)")
