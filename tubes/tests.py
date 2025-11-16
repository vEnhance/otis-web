import pytest

from core.factories import GroupFactory, UserFactory

from .factories import TubeFactory
from .models import JoinRecord


@pytest.mark.django_db
def test_active_tubes(otis):
    tube = TubeFactory.create()

    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="mallory")
    UserFactory.create(username="alice", groups=(verified_group,))

    otis.login("mallory")
    otis.get_40x("tube-list")
    otis.get_40x("tube-join", tube.pk)
    assert not JoinRecord.objects.exists()

    # TODO update this to work with the new system

    #
    #        otis.login("alice")
    #        resp = otis.get_20x("tube-list")
    #        assert tube.display_name.encode() in resp.content
    #        assert tube.main_url.encode() not in resp.content
    #
    #        resp = otis.get_40x("tube-join", tube.pk)  # redirect to join URL
    #        assert len(JoinRecord.objects.all()) == 1
    #
    #        resp = otis.get_20x("tube-list")
    #        assert tube.display_name.encode() in resp.content
    #        assert tube.main_url.encode() in resp.content
    #
    #        otis.get_40x("tube-join", tube.pk)
    #        assert len(JoinRecord.objects.all()) == 1


@pytest.mark.django_db
def test_inactive_tubes(otis):
    tube = TubeFactory.create(status="TB_HIDDEN")
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))

    otis.login("alice")
    resp = otis.get_20x("tube-list")
    otis.assert_not_has(resp, tube.display_name)
    otis.get_40x("tube-join", tube.pk)
