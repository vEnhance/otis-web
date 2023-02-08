from django.test.utils import override_settings

from core.factories import SemesterFactory, UnitFactory, UserFactory
from core.models import Semester
from core.utils import storage_hash
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import StudentFactory


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

    def test_hidden(self):
        UnitFactory.create(group__name="VisibleUnit", group__hidden=False)
        UnitFactory.create(group__name="HiddenUnit", group__hidden=True)
        resp = self.assertGet20X("catalog")
        self.assertHas(resp, "VisibleUnit")
        self.assertNotHas(resp, "HiddenUnit")
        resp = self.assertGet20X("catalog-public")
        self.assertHas(resp, "VisibleUnit")
        self.assertNotHas(resp, "HiddenUnit")

    def test_storage_hash(self):
        self.assertRegex(storage_hash("meow"), r"[0-9a-z]{64}")
        self.assertNotEqual(storage_hash("Serral"), storage_hash("Reynor"))
