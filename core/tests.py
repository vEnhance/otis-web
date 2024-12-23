from typing import Any

from django.test.utils import override_settings

from core.factories import SemesterFactory, UnitFactory, UnitGroupFactory, UserFactory
from core.models import Semester
from core.utils import storage_hash
from dashboard.factories import PSetFactory
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import StudentFactory
from rpg.factories import BonusLevelFactory


class TestCore(EvanTestCase):
    def test_semester_url(self):
        SemesterFactory.create_batch(5)
        for sem in Semester.objects.all():
            self.assertEqual(f"/dash/past/{sem.pk}/", sem.get_absolute_url())
        self.assertEqual(Semester.objects.count(), 5)

    def test_views_login_redirect(self):
        self.assertGetBecomesLoginRedirect("view-problems", 10)
        self.assertGetBecomesLoginRedirect("view-solutions", 10)
        self.assertGetBecomesLoginRedirect("view-tex", 10)
        self.assertGetBecomesLoginRedirect("catalog")

    @override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
    def test_alice_core_views(self):
        alice = StudentFactory.create()
        units = UnitFactory.create_batch(4)
        alice.curriculum.set(units[:3])
        alice.unlocked_units.set(units[:2])
        self.login(alice)

        # TODO check solutions accessible if pset submitted
        self.assertGet20X("view-problems", units[0].pk)
        self.assertGet20X("view-tex", units[0].pk)
        self.assertGetDenied("view-solutions", units[0].pk)

        # Problems accessible, but no submission yet
        self.assertGet20X("view-problems", units[1].pk)
        self.assertGet20X("view-tex", units[1].pk)
        self.assertGetDenied("view-solutions", units[1].pk)

        # Locked
        self.assertGetDenied("view-problems", units[2].pk)
        self.assertGetDenied("view-tex", units[2].pk)
        self.assertGetDenied("view-solutions", units[2].pk)
        self.assertGetDenied("view-problems", units[3].pk)
        self.assertGetDenied("view-tex", units[3].pk)
        self.assertGetDenied("view-solutions", units[3].pk)

        self.assertGet30X("admin-unit-list")

    @override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
    def test_staff_core_views(self):
        u = UnitFactory.create()
        self.login(UserFactory.create(is_staff=True))
        for v in ("view-problems", "view-tex", "view-solutions"):
            self.assertGet20X(v, u.pk)

    def test_admin_unit_list(self):
        self.login(UserFactory.create(is_staff=True, is_superuser=True))
        UnitFactory.create(group__name="Grinding", group__subject="M")
        resp = self.assertGet20X("admin-unit-list")
        self.assertHas(resp, "Grinding")

    def test_mallory_core_views(self):
        u = UnitFactory.create()
        self.login(UserFactory.create())
        for v in ("view-problems", "view-tex", "view-solutions"):
            self.assertGetDenied(v, u.pk)
        self.assertGet30X("admin-unit-list")

    def test_hidden_catalog_public(self):
        self.login(UserFactory.create())
        UnitFactory.create(group__name="VisibleUnit", group__hidden=False)
        UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
        resp = self.assertGet20X("catalog-public")
        self.assertHas(resp, "VisibleUnit")
        self.assertNotHas(resp, "HiddenUnit")

    def test_storage_hash(self):
        self.assertRegex(storage_hash("meow"), r"[0-9a-z]{64}")
        self.assertNotEqual(storage_hash("Serral"), storage_hash("Reynor"))


class TestCatalog(EvanTestCase):
    def assertCatalogEqual(
        self, query_params: dict[str, Any], expected_codes: list[str]
    ):
        # Code is strictly not a unique field but fine for our purposes
        resp = self.assertGet20X("catalog", query_params=query_params)
        unit_codes = [unit.code for unit in resp.context["units"]]
        self.assertEqual(unit_codes, expected_codes)
        return resp

    def assertCatalogEmpty(self, query_params: dict[str, Any]):
        return self.assertCatalogEqual(query_params, [])

    def test_filters(self):
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
        self.login(dora)

        resp = self.assertCatalogEqual(
            {},
            ["ZAW", "DAX", "ZAX", "BMW"],
        )
        self.assertTrue(resp.context["group_by_category"])

        self.assertCatalogEqual({"q": "UMS"}, ["DAX", "ZAX"])

        self.assertCatalogEqual(
            {"status": ["completed", "locked"]},
            ["ZAW", "BMW"],
        )
        self.assertCatalogEqual(
            {"status": "unlocked"},
            ["DAX"],
        )
        self.assertCatalogEqual(
            {"difficulty": "Z"},
            ["ZAW", "ZAX"],
        )
        self.assertCatalogEqual(
            {"difficulty": "Z", "category": "A"},
            ["ZAW", "ZAX"],
        )
        self.assertCatalogEqual(
            {"difficulty": "Z", "status": ["locked", "unlocked"]},
            ["ZAW"],
        )
        self.assertCatalogEqual(
            {"difficulty": "Z", "category": "A", "status": "locked"},
            ["ZAW"],
        )
        self.assertCatalogEqual(
            {"sort": "", "status": ["completed", "unlocked", "locked"]},
            ["ZAW", "BMW", "DAX"],
        )
        self.assertCatalogEqual(
            {"sort": "position", "category": "A"},
            ["ZAW", "DAX", "ZAX"],
        )
        self.assertCatalogEqual(
            {"sort": "-position", "difficulty": "Z"},
            ["ZAX", "ZAW"],
        )
        self.assertCatalogEqual(
            {"sort": "", "group_by_category": True},
            ["ZAW", "DAX", "ZAX", "BMW"],
        )
        self.assertCatalogEqual(
            {"sort": "-position", "group_by_category": True},
            ["ZAX", "DAX", "ZAW", "BMW"],
        )
        self.assertCatalogEqual(
            {"category": "A", "group_by_category": True},
            ["ZAW", "DAX", "ZAX"],
        )
        self.assertCatalogEqual(
            {"status": ["completed", "locked"], "group_by_category": True},
            ["ZAW", "BMW"],
        )

    def test_inactive_student(self):
        """
        Logged in user without active student account
        previously received a 500 error when filtering by status
        """
        self.login(UserFactory.create())
        self.assertCatalogEmpty({"status": "unlocked"})
        self.assertCatalogEmpty({"status": "locked"})

    def test_hidden_staff(self):
        staff = UserFactory.create(is_staff=True)
        UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
        self.login(staff)
        resp = self.assertGet20X("catalog")
        self.assertHas(resp, "HiddenUnit")

    def test_hidden_student(self):
        student = StudentFactory.create(last_level_seen=42)
        LVL35 = UnitFactory.create(code="BKV", group__hidden=True)
        LVL47 = UnitFactory.create(code="DKV", group__hidden=True)
        BonusLevelFactory.create(level=35, group=LVL35.group)
        BonusLevelFactory.create(level=47, group=LVL47.group)
        self.login(student)
        self.assertCatalogEqual({}, ["BKV"])
