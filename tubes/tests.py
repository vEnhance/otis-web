import pytest

from core.factories import GroupFactory, UserFactory

from .factories import JoinRecordFactory, TubeFactory
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


@pytest.mark.django_db
def test_inactive_tubes(otis):
    tube = TubeFactory.create(status="TB_HIDDEN")
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))

    otis.login("alice")
    resp = otis.get_20x("tube-list")
    otis.assert_not_has(resp, tube.display_name)
    otis.get_40x("tube-join", tube.pk)


@pytest.mark.django_db
def test_tube_join_existing_record(otis):
    """Test when user already has a JoinRecord for the tube."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    tube = TubeFactory.create(accepting_signups=True)
    jr = JoinRecordFactory.create(tube=tube, user=alice, invite_url="https://example.com/invite")

    otis.login(alice)
    resp = otis.get("tube-join", tube.pk)
    # Should redirect to the invite URL
    otis.assert_30x(resp)
    assert resp.url == jr.invite_url


@pytest.mark.django_db
def test_tube_join_existing_record_no_invite_url(otis):
    """Test when user has JoinRecord but no invite_url, redirects to main_url."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    tube = TubeFactory.create(accepting_signups=True, main_url="https://example.com/main")
    JoinRecordFactory.create(tube=tube, user=alice, invite_url="")

    otis.login(alice)
    resp = otis.get("tube-join", tube.pk)
    otis.assert_30x(resp)
    assert resp.url == tube.main_url


@pytest.mark.django_db
def test_tube_join_assigns_available_record(otis):
    """Test when an unclaimed JoinRecord exists, it gets assigned to the user."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    tube = TubeFactory.create(accepting_signups=True)
    jr = JoinRecordFactory.create(tube=tube, user=None, invite_url="https://example.com/join")

    otis.login(alice)
    resp = otis.get("tube-join", tube.pk)
    otis.assert_30x(resp)

    # Verify the JoinRecord was assigned to alice
    jr.refresh_from_db()
    assert jr.user == alice
    assert jr.activation_time is not None


@pytest.mark.django_db
def test_tube_join_no_available_records(otis):
    """Test when no JoinRecords are available - shows error message."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    tube = TubeFactory.create(accepting_signups=True)
    # No JoinRecords created for this tube

    otis.login(alice)
    resp = otis.get("tube-join", tube.pk, follow=True)
    otis.assert_20x(resp)
    # Should redirect to tube-list with error message
    otis.assert_has(resp, "Ran out of one-time invite codes")


@pytest.mark.django_db
def test_tube_join_not_accepting_signups(otis):
    """Test joining a tube that's not accepting signups."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    tube = TubeFactory.create(accepting_signups=False)

    otis.login(alice)
    otis.get_40x("tube-join", tube.pk)
