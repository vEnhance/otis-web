import datetime

import pytest
from django.urls import reverse
from freezegun.api import freeze_time

from core.factories import SemesterFactory, UnitFactory, UserFactory
from core.models import Unit
from dashboard.factories import PSetFactory
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    StudentFactory,
    UnitPetitionFactory,
)
from roster.models import Student, StudentStanding, UnitPetition


def ordinary_unit() -> Unit:
    """A unit that is not secret; UnitFactory otherwise picks the subject
    at random, and secret (K) units skip the usual unlock limits."""
    return UnitFactory.create(group__subject="A")


def petition(otis, student: Student, unit: Unit, action: str, explanation: str = "hi"):
    return otis.post(
        "petition",
        student.pk,
        data={"unit": unit.pk, "action_type": action, "explanation": explanation},
        follow=True,
    )


def past_unlock_petitions(student: Student, count: int) -> None:
    UnitPetitionFactory.create_batch(
        count, student=student, unit__group__subject="A", status="PET_ACC"
    )


def latest_petition(student: Student) -> UnitPetition:
    return UnitPetition.objects.filter(student=student).latest("pk")


@pytest.mark.django_db
def test_legacy_inquiry_url_redirects_to_petition(otis) -> None:
    alice = StudentFactory.create()
    otis.login(alice)
    resp = otis.client.get(f"/roster/inquiry/{alice.pk}/")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("petition", args=(alice.pk,))


@pytest.mark.django_db
def test_petition_form_marks_completed_units(otis) -> None:
    alice = StudentFactory.create()
    past = StudentFactory.create(
        user=alice.user, semester=SemesterFactory.create(active=False)
    )
    done_now, done_past, pending, untouched = UnitFactory.create_batch(4)
    PSetFactory.create(student=alice, unit=done_now, status="A")
    PSetFactory.create(student=past, unit=done_past, status="A")
    PSetFactory.create(student=alice, unit=pending, status="P")
    otis.login(alice)

    resp = otis.get_20x("petition", alice.pk)
    field = resp.context["form"].fields["unit"]
    assert field.completed_pks == {done_now.pk, done_past.pk}
    marked = {
        unit.pk: field.label_from_instance(unit).startswith("✔")
        for unit in (done_now, done_past, pending, untouched)
    }
    assert marked == {
        done_now.pk: True,
        done_past.pk: True,
        pending.pk: False,
        untouched.pk: False,
    }


@pytest.mark.django_db
def test_petition_rejects_invalid_unit(otis) -> None:
    alice = StudentFactory.create()
    otis.login(alice)
    resp = otis.post_20x(
        "petition",
        alice.pk,
        data={"unit": "invalid", "action_type": "PET_ACT_UNLOCK", "explanation": "hi"},
    )
    assert "unit" in resp.context["form"].errors
    assert not UnitPetition.objects.exists()


@pytest.mark.django_db
def test_unlock_auto_accepted_for_new_student(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 5)
    unit = ordinary_unit()
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_UNLOCK"),
        "Petition automatically processed.",
    )
    pet = latest_petition(alice)
    assert pet.was_auto_processed
    assert pet.status == "PET_ACC"
    assert alice.curriculum.contains(unit)
    assert alice.unlocked_units.contains(unit)


@pytest.mark.django_db
def test_unlock_waits_after_six_petitions(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 6)
    unit = ordinary_unit()
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_UNLOCK"),
        "Petition submitted, wait for it!",
    )
    pet = latest_petition(alice)
    assert not pet.was_auto_processed
    assert pet.status == "PET_NEW"
    assert not alice.unlocked_units.contains(unit)


@pytest.mark.django_db
def test_secret_unit_unlock_auto_accepted(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 6)
    secret_unit = UnitFactory.create(
        code="BKV",
        group__name="Spooky Unit",
        group__subject="K",
        group__hidden=True,
    )
    alice.curriculum.add(secret_unit)
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, secret_unit, "PET_ACT_UNLOCK"),
        "Petition automatically processed.",
    )
    assert latest_petition(alice).status == "PET_ACC"
    assert alice.unlocked_units.contains(secret_unit)


@pytest.mark.django_db
def test_unlock_rejected_past_nine_unlocked_units(otis) -> None:
    alice = StudentFactory.create()
    units = [ordinary_unit() for _ in range(9)]
    alice.curriculum.set(units)
    alice.unlocked_units.set(units)
    unit = ordinary_unit()
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_UNLOCK"),
        "You can't have more than 9 unfinished units unlocked at once.",
    )
    pet = latest_petition(alice)
    assert pet.was_auto_processed
    assert pet.status == "PET_REJ"
    assert alice.unlocked_units.count() == 9


@pytest.mark.django_db
def test_append_auto_accepted(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 8)
    unit = ordinary_unit()
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_APPEND"),
        "Petition automatically processed.",
    )
    assert latest_petition(alice).status == "PET_ACC"
    assert alice.curriculum.contains(unit)
    assert not alice.unlocked_units.contains(unit)


@pytest.mark.django_db
def test_drop_of_locked_unit_auto_accepted(otis) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_DROP"),
        "Petition automatically processed.",
    )
    assert latest_petition(alice).status == "PET_ACC"
    assert not alice.curriculum.contains(unit)


@pytest.mark.django_db
def test_drop_of_unlocked_unit_waits(otis) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    alice.unlocked_units.add(unit)
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_DROP"),
        "Petition submitted, wait for it!",
    )
    assert latest_petition(alice).status == "PET_NEW"
    assert alice.curriculum.contains(unit)


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["PET_ACT_DROP", "PET_ACT_LOCK"])
def test_drop_or_lock_rejected_with_pending_submission(otis, action: str) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    alice.unlocked_units.add(unit)
    PSetFactory.create(student=alice, unit=unit, status="P")
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, action),
        "You have a pending submission for this unit.",
    )
    pet = latest_petition(alice)
    assert pet.was_auto_processed
    assert pet.status == "PET_REJ"
    assert alice.unlocked_units.contains(unit)


@pytest.mark.django_db
def test_lock_rejected_with_accepted_submission(otis) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    alice.unlocked_units.add(unit)
    PSetFactory.create(student=alice, unit=unit, status="A")
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_LOCK"),
        "You can't lock units with accepted submissions.",
    )
    assert latest_petition(alice).status == "PET_REJ"
    assert alice.unlocked_units.contains(unit)


@pytest.mark.django_db
def test_many_unlock_petitions_put_on_hold(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 11)
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_DROP"),
        "You have submitted an abnormally large number of petitions "
        "so you should contact Evan specially to explain why.",
    )
    pet = latest_petition(alice)
    assert not pet.was_auto_processed
    assert pet.status == "PET_HOLD"
    assert alice.curriculum.contains(unit)


@pytest.mark.django_db
def test_psets_raise_hold_threshold(otis) -> None:
    alice = StudentFactory.create()
    past_unlock_petitions(alice, 11)
    PSetFactory.create_batch(30, student=alice)
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    otis.login(alice)

    otis.assert_message(
        petition(otis, alice, unit, "PET_ACT_DROP"),
        "Petition automatically processed.",
    )
    assert latest_petition(alice).status == "PET_ACC"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "already_unlocked", "in_curriculum", "unlocked"),
    [
        ("PET_ACT_UNLOCK", False, True, True),
        ("PET_ACT_APPEND", False, True, False),
        ("PET_ACT_LOCK", True, True, False),
        ("PET_ACT_DROP", True, False, False),
    ],
)
def test_instructor_petition_auto_accepted(
    otis, action: str, already_unlocked: bool, in_curriculum: bool, unlocked: bool
) -> None:
    firefly = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[firefly])
    past_unlock_petitions(alice, 20)
    unit = ordinary_unit()
    if already_unlocked:
        alice.curriculum.add(unit)
        alice.unlocked_units.add(unit)
    otis.login(firefly)

    otis.assert_message(
        petition(otis, alice, unit, action), "Petition automatically processed."
    )
    pet = latest_petition(alice)
    assert pet.was_auto_processed
    assert pet.status == "PET_ACC"
    assert alice.curriculum.contains(unit) is in_curriculum
    assert alice.unlocked_units.contains(unit) is unlocked


@pytest.mark.django_db
@pytest.mark.parametrize(
    "student_kwargs",
    [
        {"semester__active": False},
        {"standing": StudentStanding.DROPPED},
        {"standing": StudentStanding.NEWBORN},
    ],
)
def test_petition_form_denied(otis, student_kwargs) -> None:
    alice = StudentFactory.create(**student_kwargs)
    otis.login(alice)
    otis.get_denied("petition", alice.pk)


@pytest.mark.django_db
def test_petition_form_denied_when_delinquent(otis) -> None:
    eve = StudentFactory.create(
        semester__show_invoices=True,
        semester__half_payment_deadline=datetime.datetime(
            2021, 7, 1, tzinfo=datetime.UTC
        ),
    )
    with freeze_time("2021-06-20", tz_offset=0):
        InvoiceFactory.create(student=eve)
    otis.login(eve)
    with freeze_time("2021-07-30", tz_offset=0):
        otis.get_denied("petition", eve.pk)


@pytest.mark.django_db
def test_petition_cant_rapid_fire(otis) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    otis.login(alice)
    with freeze_time("2025-10-31", tz_offset=0):
        otis.assert_message(
            petition(otis, alice, unit, "PET_ACT_UNLOCK"),
            "Petition automatically processed.",
        )
        otis.assert_message(
            petition(otis, alice, unit, "PET_ACT_UNLOCK", "trigger happy"),
            "The same petition already was submitted within the last 90 seconds.",
        )
    assert UnitPetition.objects.filter(student=alice).count() == 1


@pytest.mark.django_db
def test_petition_cant_rapid_fire_after_auto_reject(otis) -> None:
    """A double submit is caught even when the first copy was auto-rejected."""
    alice = StudentFactory.create()
    unit = ordinary_unit()
    alice.curriculum.add(unit)
    alice.unlocked_units.add(unit)
    PSetFactory.create(student=alice, unit=unit, status="P")
    otis.login(alice)
    with freeze_time("2025-10-31", tz_offset=0):
        otis.assert_message(
            petition(otis, alice, unit, "PET_ACT_DROP"),
            "You have a pending submission for this unit.",
        )
        otis.assert_message(
            petition(otis, alice, unit, "PET_ACT_DROP"),
            "The same petition already was submitted within the last 90 seconds.",
        )
    assert UnitPetition.objects.filter(student=alice).count() == 1


@pytest.mark.django_db
def test_petition_can_resubmit_after_cancel(otis) -> None:
    alice = StudentFactory.create()
    unit = ordinary_unit()
    otis.login(alice)
    with freeze_time("2025-10-31", tz_offset=0):
        UnitPetitionFactory.create(student=alice, unit=unit, status="PET_CANC")
        otis.assert_message(
            petition(otis, alice, unit, "PET_ACT_UNLOCK"),
            "Petition automatically processed.",
        )
    assert UnitPetition.objects.filter(student=alice).count() == 2


@pytest.mark.django_db
def test_cancel_petition(otis) -> None:
    alice = StudentFactory.create()
    pet = UnitPetitionFactory.create(student=alice, status="PET_NEW")
    otis.login(alice)
    otis.assert_message(
        otis.post_20x("petition-cancel", pet.pk, follow=True),
        "Petition successfully canceled.",
    )
    pet.refresh_from_db()
    assert pet.status == "PET_CANC"


@pytest.mark.django_db
def test_cancel_petition_rejects_get(otis) -> None:
    alice = StudentFactory.create()
    pet = UnitPetitionFactory.create(student=alice, status="PET_NEW")
    otis.login(alice)
    # a cross-site navigation is a GET, so canceling can't be reachable that way
    assert otis.get("petition-cancel", pet.pk).status_code == 405
    pet.refresh_from_db()
    assert pet.status == "PET_NEW"


@pytest.mark.django_db
def test_cancel_petition_of_other_student_denied(otis) -> None:
    pet = UnitPetitionFactory.create(status="PET_NEW")
    otis.login(StudentFactory.create())
    otis.post_40x("petition-cancel", pet.pk)
    pet.refresh_from_db()
    assert pet.status == "PET_NEW"


@pytest.mark.django_db
def test_staff_can_cancel_any_petition(otis) -> None:
    pet = UnitPetitionFactory.create(status="PET_NEW")
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.post_20x("petition-cancel", pet.pk, follow=True)
    pet.refresh_from_db()
    assert pet.status == "PET_CANC"


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["PET_ACC", "PET_REJ", "PET_HOLD", "PET_CANC"])
def test_cannot_cancel_non_pending(otis, status: str) -> None:
    alice = StudentFactory.create()
    pet = UnitPetitionFactory.create(student=alice, status=status)
    otis.login(alice)
    otis.post_40x("petition-cancel", pet.pk)
    pet.refresh_from_db()
    assert pet.status == status


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["PET_ACC", "PET_REJ", "PET_HOLD", "PET_CANC"])
def test_petition_page_with_past_petition(otis, status: str) -> None:
    alice = StudentFactory.create()
    UnitPetitionFactory.create(student=alice, status=status)
    otis.login(alice)
    otis.get_20x("petition", alice.pk)
