import pytest
from django.contrib.messages import constants as message_levels

from core.factories import UnitFactory, UnitGroupFactory
from core.models import Unit
from dashboard.factories import PSetFactory
from roster.factories import AssistantFactory, StudentFactory
from roster.models import Student, StudentStanding


@pytest.fixture
def mystery_student() -> tuple[Student, Unit, Unit]:
    """A student with Mystery unlocked, and the unit two positions after it."""
    mystery = UnitFactory.create(group__name="Mystery")
    added_unit = UnitFactory.create_batch(2)[1]
    alice = StudentFactory.create()
    alice.curriculum.set([mystery])
    alice.unlocked_units.set([mystery])
    return alice, mystery, added_unit


@pytest.mark.django_db
def test_mystery_unlock_requires_mystery_unit(otis) -> None:
    UnitFactory.create(group__name="Mystery")
    otis.login(StudentFactory.create())
    otis.assert_response_denied(
        otis.client.post("/roster/mystery-unlock/easier/", follow=True)
    )


@pytest.mark.django_db
def test_mystery_unlock_swaps_in_later_unit(otis, mystery_student) -> None:
    alice, mystery, added_unit = mystery_student
    otis.login(alice)

    resp = otis.client.post("/roster/mystery-unlock/harder/", follow=True)
    otis.assert_response_20x(resp)
    assert not alice.curriculum.contains(mystery)
    assert not alice.unlocked_units.contains(mystery)
    assert alice.curriculum.contains(added_unit)
    assert alice.unlocked_units.contains(added_unit)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])


@pytest.mark.django_db
def test_mystery_unlock_get_only_confirms(otis, mystery_student) -> None:
    alice, mystery, _ = mystery_student
    otis.login(alice)

    resp = otis.client.get("/roster/mystery-unlock/harder/")
    otis.assert_response_20x(resp)
    assert resp.context["delta"] == 2
    assert alice.curriculum.contains(mystery)
    assert alice.unlocked_units.contains(mystery)


@pytest.mark.django_db
def test_mystery_unlock_clears_pending_next_unit(otis, mystery_student) -> None:
    """https://github.com/vEnhance/otis-web/issues/447"""
    alice, mystery, added_unit = mystery_student
    pset = PSetFactory.create(
        student=alice, unit=mystery, status="P", next_unit_to_unlock=added_unit
    )
    otis.login(alice)

    otis.assert_response_20x(
        otis.client.post("/roster/mystery-unlock/harder/", follow=True)
    )
    pset.refresh_from_db()
    assert pset.next_unit_to_unlock is None


@pytest.mark.django_db
def test_advance_denied_to_student(otis) -> None:
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    otis.login(alice)
    otis.get_denied("advance", alice.pk)


@pytest.mark.django_db
def test_advance_page_loads_for_instructor(otis) -> None:
    firefly = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[firefly])
    otis.login(firefly)
    otis.get_20x("advance", alice.pk)


@pytest.mark.django_db
def test_advance_rejects_invalid_unit(otis) -> None:
    firefly = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[firefly])
    unit = UnitFactory.create()
    otis.login(firefly)

    resp = otis.post_20x(
        "advance",
        alice.pk,
        data={"units_to_unlock": ["invalid"], "units_to_add": [unit.pk]},
    )
    assert "units_to_unlock" in resp.context["form"].errors
    assert not alice.curriculum.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "already_unlocked", "in_curriculum", "unlocked"),
    [
        ("units_to_unlock", False, True, True),
        ("units_to_open", False, True, True),
        ("units_to_add", False, True, False),
        ("units_to_lock", True, True, False),
        ("units_to_drop", True, False, False),
    ],
)
def test_advance_action(
    otis, field: str, already_unlocked: bool, in_curriculum: bool, unlocked: bool
) -> None:
    firefly = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[firefly])
    unit = UnitFactory.create()
    if already_unlocked:
        alice.curriculum.add(unit)
        alice.unlocked_units.add(unit)
    otis.login(firefly)

    resp = otis.post_20x("advance", alice.pk, data={field: [unit.pk]})
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    assert alice.curriculum.contains(unit) is in_curriculum
    assert alice.unlocked_units.contains(unit) is unlocked


def make_unit_groups(count: int) -> None:
    for unitgroup in UnitGroupFactory.create_batch(count):
        for letter in "BDZ":
            UnitFactory.create(
                code=letter + unitgroup.subject[0] + "W", group=unitgroup
            )


def first_unit_of_each_group(form) -> dict[str, list[int]]:
    return {
        name: [field.choices[0][0]]
        for name, field in form.fields.items()
        if name.startswith("group-")
    }


@pytest.mark.django_db
def test_curriculum_read_only_for_student(otis) -> None:
    alice = StudentFactory.create(assistants=[AssistantFactory.create()])
    make_unit_groups(2)
    otis.login(alice)

    resp = otis.get_20x("currshow", alice.pk)
    assert not resp.context["enabled"]
    otis.post_20x(
        "currshow", alice.pk, data=first_unit_of_each_group(resp.context["form"])
    )
    assert not alice.curriculum.exists()


@pytest.mark.django_db
def test_curriculum_rejects_invalid_choice(otis) -> None:
    staff = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[staff])
    make_unit_groups(2)
    otis.login(staff)

    resp = otis.get_20x("currshow", alice.pk)
    assert resp.context["enabled"]
    otis.post_20x("currshow", alice.pk, data={"group-0": ["invalid"]})
    assert not alice.curriculum.exists()


@pytest.mark.django_db
def test_curriculum_saved_by_instructor(otis) -> None:
    staff = AssistantFactory.create()
    alice = StudentFactory.create(assistants=[staff])
    make_unit_groups(4)
    otis.login(staff)

    form = otis.get_20x("currshow", alice.pk).context["form"]
    data = first_unit_of_each_group(form)
    resp = otis.post_20x("currshow", alice.pk, data=data)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    assert set(alice.curriculum.values_list("pk", flat=True)) == {
        pk for pks in data.values() for pk in pks
    }


@pytest.mark.django_db
def test_curriculum_archived_semester(otis) -> None:
    alice = StudentFactory.create(
        standing=StudentStanding.NEWBORN, semester__active=False
    )
    make_unit_groups(2)
    otis.login(alice)

    resp = otis.get_20x("currshow", alice.pk)
    assert not resp.context["enabled"]
    otis.post("currshow", alice.pk, data=first_unit_of_each_group(resp.context["form"]))
    assert not alice.curriculum.exists()


@pytest.mark.django_db
def test_finalize_without_units(otis) -> None:
    alice = StudentFactory.create(standing=StudentStanding.NEWBORN)
    otis.login(alice)
    otis.assert_message(
        otis.post("finalize", alice.pk, follow=True),
        "You didn't select any units. "
        "You should select some units before using this link.",
    )
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.NEWBORN


@pytest.mark.django_db
def test_finalize_unlocks_first_three_units(otis) -> None:
    alice = StudentFactory.create(standing=StudentStanding.NEWBORN)
    alice.curriculum.set(UnitFactory.create_batch(20))
    otis.login(alice)

    otis.post_30x("finalize", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.GOOD
    assert alice.unlocked_units.count() == 3


@pytest.mark.django_db
def test_finalize_only_once(otis) -> None:
    alice = StudentFactory.create(standing=StudentStanding.GOOD)
    alice.curriculum.set(UnitFactory.create_batch(5))
    otis.login(alice)
    otis.post_40x("finalize", alice.pk)
    assert not alice.unlocked_units.exists()


@pytest.mark.django_db
def test_finalize_rejects_get(otis) -> None:
    alice = StudentFactory.create(standing=StudentStanding.NEWBORN)
    alice.curriculum.set(UnitFactory.create_batch(5))
    otis.login(alice)
    otis.get_40x("finalize", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.NEWBORN


@pytest.mark.django_db
def test_finalize_archived_semester(otis) -> None:
    alice = StudentFactory.create(
        standing=StudentStanding.NEWBORN, semester__active=False
    )
    alice.curriculum.set(UnitFactory.create_batch(5))
    otis.login(alice)
    otis.post_40x("finalize", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.NEWBORN
