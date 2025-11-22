import datetime

import pytest
from freezegun import freeze_time

from core.factories import GroupFactory, UserFactory
from hanabi.factories import HanabiContestFactory, HanabiReplayFactory
from hanabi.models import HanabiContest, HanabiPlayer

UTC = datetime.timezone.utc


@pytest.mark.django_db
def test_contest():
    contest: HanabiContest = HanabiContestFactory.create(
        pk=1,
        variant_name="Duck (5 Suits)",
        variant_id=55,
        start_date=datetime.datetime(2050, 2, 1, tzinfo=UTC),
        end_date=datetime.datetime(2050, 2, 14, tzinfo=UTC),
    )
    with freeze_time("2050-01-01", tz_offset=0):
        assert not contest.has_ended
    with freeze_time("2050-02-01", tz_offset=0):
        assert not contest.has_ended
    with freeze_time("2050-02-15", tz_offset=0):
        assert contest.has_ended
    assert contest.create_table_url == (
        r"https://hanab.live/create-table?name=%21seed+otis1"
        r"&variantName=Duck+%285+Suits%29"
        r"&timed=true&timeBase=180&timePerTurn=30"
    )
    assert contest.hanab_stats_page_url == "https://hanab.live/seed/p3v55sotis1"
    assert contest.max_score == 25

    replay = HanabiReplayFactory.create(contest=contest, game_score=23)
    assert abs(replay.get_base_spades() - 2.86557184) < 1e-6


@pytest.mark.django_db
def test_contest_list(otis):
    HanabiContestFactory.create(
        variant_name="Candy Corn Mix (5 Suits)",
        variant_id=2016,
        start_date=datetime.datetime(2050, 10, 15, tzinfo=UTC),
        end_date=datetime.datetime(2050, 11, 15, tzinfo=UTC),
    )
    HanabiContestFactory.create(
        variant_name="Holiday Mix (5 Suits)",
        variant_id=2018,
        start_date=datetime.datetime(2050, 12, 1, tzinfo=UTC),
        end_date=datetime.datetime(2050, 12, 31, tzinfo=UTC),
    )
    HanabiContestFactory.create(
        variant_name="Valentine Mix (5 Suits)",
        variant_id=2069,
        start_date=datetime.datetime(2050, 2, 1, tzinfo=UTC),
        end_date=datetime.datetime(2050, 2, 28, tzinfo=UTC),
    )

    with freeze_time("2050-10-31", tz_offset=0):
        resp = otis.get_20x("hanabi-contests")
        assert resp.content.count(b"Candy Corn Mix") == 2
        otis.assert_has(resp, "Valentine Mix")
        otis.assert_not_has(resp, "Holiday Mix")


@pytest.mark.django_db
def test_register(otis):
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="mallory")
    UserFactory.create(username="alice", groups=(verified_group,))

    otis.login("mallory")
    otis.get_40x("hanabi-register")
    otis.post_40x("hanabi-register", data={"hanab_username": "mallory"})

    otis.login("alice")
    resp = otis.get_20x("hanabi-register")
    otis.assert_not_has(resp, "You already registered")
    resp = otis.post_20x(
        "hanabi-register", data={"hanab_username": "alice"}, follow=True
    )
    otis.assert_has(resp, "You set your username to alice.")
    assert HanabiPlayer.objects.filter(
        user__username="alice", hanab_username="alice"
    ).exists()

    resp = otis.get_20x("hanabi-register", follow=True)
    otis.assert_has(resp, "You already registered")
    resp = otis.post_20x(
        "hanabi-register", data={"hanab_username": "alice"}, follow=True
    )
    otis.assert_has(resp, "You already registered")


@pytest.mark.django_db
def test_replay_list(otis):
    """Test viewing the replay list for a contest."""
    contest = HanabiContestFactory.create(
        pk=42,
        variant_name="Rainbow (5 Suits)",
        variant_id=15,
        start_date=datetime.datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2024, 1, 14, tzinfo=UTC),
        processed=True,  # Contest results are processed
    )

    # Create some replays
    HanabiReplayFactory.create(contest=contest, game_score=25, turn_count=40)
    HanabiReplayFactory.create(contest=contest, game_score=24, turn_count=42)
    HanabiReplayFactory.create(contest=contest, game_score=20, turn_count=35)

    # View the replays list
    resp = otis.get_20x("hanabi-replays", contest.pk)
    assert len(resp.context["replays"]) == 3
    assert resp.context["contest"] == contest


@pytest.mark.django_db
def test_replay_list_unprocessed(otis):
    """Test that unprocessed contest results are not visible to non-staff."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    contest = HanabiContestFactory.create(
        pk=99,
        start_date=datetime.datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2024, 1, 14, tzinfo=UTC),
        processed=False,  # Contest not processed yet
    )

    # Non-staff user cannot view unprocessed results
    otis.login(alice)
    otis.get_40x("hanabi-replays", contest.pk)

    # Staff can view unprocessed results
    otis.login(admin)
    resp = otis.get_20x("hanabi-replays", contest.pk)
    assert resp.context["contest"] == contest


@pytest.mark.django_db
def test_replay_list_with_participation(otis):
    """Test replay list shows own_replay when user participated."""
    from hanabi.factories import HanabiParticipationFactory, HanabiPlayerFactory

    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))

    contest = HanabiContestFactory.create(
        pk=77,
        start_date=datetime.datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime.datetime(2024, 1, 14, tzinfo=UTC),
        processed=True,
    )

    # Create a replay with Alice's participation
    player = HanabiPlayerFactory.create(user=alice)
    replay = HanabiReplayFactory.create(contest=contest, game_score=22)
    HanabiParticipationFactory.create(player=player, replay=replay)

    otis.login(alice)
    resp = otis.get_20x("hanabi-replays", contest.pk)
    assert resp.context["own_replay"] == replay


@pytest.mark.django_db
def test_hanabi_upload(otis):
    """Test the hanabi_upload admin view."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    contest = HanabiContestFactory.create(pk=55)

    # Non-admin cannot access
    otis.login(alice)
    otis.get_40x("hanabi-upload", contest.pk)

    # Admin can access (even though it's not implemented)
    otis.login(admin)
    resp = otis.get_20x("hanabi-upload", contest.pk)
    otis.assert_has(resp, "Not implemented")
