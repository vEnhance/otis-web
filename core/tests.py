import re
from typing import Any

import pytest
from django.test.utils import override_settings

from core.factories import (
    GroupFactory,
    SemesterFactory,
    UnitFactory,
    UnitGroupFactory,
    UserFactory,
)
from core.models import Semester
from core.utils import storage_hash
from dashboard.factories import PSetFactory
from roster.factories import StudentFactory
from rpg.factories import BonusLevelFactory


@pytest.mark.django_db
def test_semester_url():
    SemesterFactory.create_batch(5)
    for sem in Semester.objects.all():
        assert f"/dash/past/{sem.pk}/" == sem.get_absolute_url()
    assert Semester.objects.count() == 5


@pytest.mark.django_db
def test_views_login_redirect(otis):
    otis.get_login_redirect("view-problems", 10)
    otis.get_login_redirect("view-solutions", 10)
    otis.get_login_redirect("view-tex", 10)
    otis.get_login_redirect("catalog")


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_alice_core_views(otis):
    alice = StudentFactory.create()
    units = UnitFactory.create_batch(4)
    alice.curriculum.set(units[:3])
    alice.unlocked_units.set(units[:2])
    otis.login(alice)

    # TODO check solutions accessible if pset submitted
    otis.get_20x("view-problems", units[0].pk)
    otis.get_20x("view-tex", units[0].pk)
    otis.get_denied("view-solutions", units[0].pk)

    # Problems accessible, but no submission yet
    otis.get_20x("view-problems", units[1].pk)
    otis.get_20x("view-tex", units[1].pk)
    otis.get_denied("view-solutions", units[1].pk)

    # Locked
    otis.get_denied("view-problems", units[2].pk)
    otis.get_denied("view-tex", units[2].pk)
    otis.get_denied("view-solutions", units[2].pk)
    otis.get_denied("view-problems", units[3].pk)
    otis.get_denied("view-tex", units[3].pk)
    otis.get_denied("view-solutions", units[3].pk)

    otis.get_40x("admin-unit-list")


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_staff_core_views(otis):
    u = UnitFactory.create()
    otis.login(UserFactory.create(is_staff=True))
    for v in ("view-problems", "view-tex", "view-solutions"):
        otis.get_20x(v, u.pk)


@pytest.mark.django_db
def test_sorted_unit_list(otis):
    otis.login(UserFactory.create())
    UnitFactory.create(group__name="VisibleUnit", group__hidden=False)
    UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
    resp = otis.get_20x("sorted-unit-list")
    otis.assert_has(resp, "VisibleUnit")
    otis.assert_not_has(resp, "HiddenUnit")


@pytest.mark.django_db
def test_admin_unit_list(otis):
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    UnitFactory.create(group__name="Grinding", group__subject="M")
    resp = otis.get_20x("admin-unit-list")
    otis.assert_has(resp, "Grinding")


@pytest.mark.django_db
def test_mallory_core_views(otis):
    u = UnitFactory.create()
    otis.login(UserFactory.create())
    for v in ("view-problems", "view-tex", "view-solutions"):
        otis.get_denied(v, u.pk)
    otis.get_40x("admin-unit-list")


@pytest.mark.django_db
def test_hidden_catalog_public(otis):
    otis.login(UserFactory.create())
    UnitFactory.create(group__name="VisibleUnit", group__hidden=False)
    UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
    resp = otis.get_20x("catalog-public")
    otis.assert_has(resp, "VisibleUnit")
    otis.assert_not_has(resp, "HiddenUnit")


@pytest.mark.django_db
def test_storage_hash():
    # In test mode, storage_hash returns "TESTING_" prefix
    assert re.match(r"(TESTING_)?[0-9a-z]{64}", storage_hash("meow"))
    assert storage_hash("Serral") != storage_hash("Reynor")


@pytest.mark.django_db
def test_calendar(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)

    # no active semester, so this should 404
    otis.get_40x("calendar")

    # still 404's since no calendar provided
    sem = SemesterFactory.create(active=True)
    otis.get_40x("calendar")

    # add a calendar URL, now it should work
    sem.calendar_url = "https://www.example.org"
    sem.save()
    resp = otis.get_30x("calendar")
    assert resp.headers["Location"] == "https://www.example.org"


# Helper functions for catalog tests
def assert_catalog_equal(
    otis, query_params: dict[str, Any], expected_codes: list[str]
):
    # Code is strictly not a unique field but fine for our purposes
    resp = otis.get_20x("catalog", query_params=query_params)
    unit_codes = [unit.code for unit in resp.context["units"]]
    assert unit_codes == expected_codes
    return resp


def assert_catalog_empty(otis, query_params: dict[str, Any]):
    return assert_catalog_equal(otis, query_params, [])


@pytest.mark.django_db
def test_filters(otis):
    # TODO: one thing this does not test is sorting by num completions
    # TODO: clean this up
    GRINDING = UnitGroupFactory.create(name="Grinding", subject="M")
    ANALYSIS = UnitGroupFactory.create(name="Analysis", subject="A")
    SUMS = UnitGroupFactory.create(name="Sums", subject="A")

    BMW = UnitFactory.create(code="BMW", position=1, group=GRINDING)  # Completed
    ZAW = UnitFactory.create(code="ZAW", position=2, group=ANALYSIS)  # Locked
    DAX = UnitFactory.create(code="DAX", position=3, group=SUMS)  # Unlocked
    ZAX = UnitFactory.create(code="ZAX", position=4, group=SUMS)  # NA

    dora = StudentFactory.create()
    dora.curriculum.set([BMW, DAX, ZAW])
    dora.unlocked_units.set([BMW, DAX])
    PSetFactory.create(student=dora, unit=BMW, next_unit_to_unlock=ZAX)
    otis.login(dora)

    resp = assert_catalog_equal(
        otis,
        {},
        ["ZAW", "DAX", "ZAX", "BMW"],
    )
    assert resp.context["group_by_category"]

    assert_catalog_equal(otis, {"q": "UMS"}, ["DAX", "ZAX"])

    assert_catalog_equal(
        otis,
        {"status": ["completed", "locked"]},
        ["ZAW", "BMW"],
    )
    assert_catalog_equal(
        otis,
        {"status": "unlocked"},
        ["DAX"],
    )
    assert_catalog_equal(
        otis,
        {"difficulty": "Z"},
        ["ZAW", "ZAX"],
    )
    assert_catalog_equal(
        otis,
        {"difficulty": "Z", "category": "A"},
        ["ZAW", "ZAX"],
    )
    assert_catalog_equal(
        otis,
        {"difficulty": "Z", "status": ["locked", "unlocked"]},
        ["ZAW"],
    )
    assert_catalog_equal(
        otis,
        {"difficulty": "Z", "category": "A", "status": "locked"},
        ["ZAW"],
    )
    assert_catalog_equal(
        otis,
        {"sort": "", "status": ["completed", "unlocked", "locked"]},
        ["ZAW", "BMW", "DAX"],
    )
    assert_catalog_equal(
        otis,
        {"sort": "position", "category": "A"},
        ["ZAW", "DAX", "ZAX"],
    )
    assert_catalog_equal(
        otis,
        {"sort": "-position", "difficulty": "Z"},
        ["ZAX", "ZAW"],
    )
    assert_catalog_equal(
        otis,
        {"sort": "", "group_by_category": True},
        ["ZAW", "DAX", "ZAX", "BMW"],
    )
    assert_catalog_equal(
        otis,
        {"sort": "-position", "group_by_category": True},
        ["ZAX", "DAX", "ZAW", "BMW"],
    )
    assert_catalog_equal(
        otis,
        {"category": "A", "group_by_category": True},
        ["ZAW", "DAX", "ZAX"],
    )
    assert_catalog_equal(
        otis,
        {"status": ["completed", "locked"], "group_by_category": True},
        ["ZAW", "BMW"],
    )


@pytest.mark.django_db
def test_inactive_student(otis):
    """
    Logged in user without active student account
    previously received a 500 error when filtering by status
    """
    otis.login(UserFactory.create())
    assert_catalog_empty(otis, {"status": "unlocked"})
    assert_catalog_empty(otis, {"status": "locked"})


@pytest.mark.django_db
def test_hidden_staff(otis):
    staff = UserFactory.create(is_staff=True)
    UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
    otis.login(staff)
    resp = otis.get_20x("catalog")
    otis.assert_has(resp, "HiddenUnit")


@pytest.mark.django_db
def test_hidden_student(otis):
    student = StudentFactory.create()
    student.curriculum.set(
        [UnitFactory.create(code="BCW", group__hidden=True)]
    )  # Hidden unit in curriculum
    UnitFactory.create(
        code="DAW", group__hidden=True
    )  # Hidden unit not in curriculum
    otis.login(student)
    assert_catalog_equal(otis, {}, ["BCW"])


@pytest.mark.django_db
def test_bonus_student(otis):
    student = StudentFactory.create(last_level_seen=42)
    BonusLevelFactory.create(
        level=35, group=UnitFactory.create(code="BKV", group__hidden=True).group
    )  # Unlocked bonus level
    BonusLevelFactory.create(
        level=47, group=UnitFactory.create(code="DKV", group__hidden=True).group
    )  # Locked bonus level
    otis.login(student)
    assert_catalog_equal(otis, {}, ["BKV"])
