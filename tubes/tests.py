from core.factories import GroupFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase

from .factories import TubeFactory
from .models import JoinRecord


class TubeTests(EvanTestCase):
    def test_active_tubes(self) -> None:
        tube = TubeFactory.create()

        verified_group = GroupFactory(name="Verified")
        UserFactory.create(username="mallory")
        UserFactory.create(username="alice", groups=(verified_group,))

        self.login("mallory")
        self.assertGet40X("tube-list")
        self.assertGet40X("tube-join", tube.pk)
        self.assertFalse(JoinRecord.objects.exists())

        # TODO update this to work with the new system

    #
    #        self.login("alice")
    #        resp = self.assertGet20X("tube-list")
    #        self.assertContains(resp, tube.display_name)
    #        self.assertNotContains(resp, tube.main_url)
    #
    #        resp = self.assertGet40X("tube-join", tube.pk)  # redirect to join URL
    #        self.assertEqual(len(JoinRecord.objects.all()), 1)
    #
    #        resp = self.assertGet20X("tube-list")
    #        self.assertContains(resp, tube.display_name)
    #        self.assertContains(resp, tube.main_url)
    #
    #        self.assertGet40X("tube-join", tube.pk)
    #        self.assertEqual(len(JoinRecord.objects.all()), 1)

    def test_inactive_tubes(self) -> None:
        tube = TubeFactory.create(status="TB_HIDDEN")
        verified_group = GroupFactory(name="Verified")
        UserFactory.create(username="alice", groups=(verified_group,))

        self.login("alice")
        resp = self.assertGet20X("tube-list")
        self.assertNotContains(resp, tube.display_name)
        self.assertGet40X("tube-join", tube.pk)
