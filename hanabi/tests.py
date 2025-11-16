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
