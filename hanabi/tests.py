import datetime

from django.utils import timezone
from freezegun import freeze_time

from core.factories import GroupFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase
from hanabi.factories import HanabiContestFactory, HanabiReplayFactory
from hanabi.models import HanabiContest, HanabiPlayer

UTC = timezone.utc


class HanabiModelTests(EvanTestCase):
    def test_contest(self) -> None:
        contest: HanabiContest = HanabiContestFactory.create(
            pk=1,
            variant_name="Duck (5 Suits)",
            variant_id=55,
            start_date=datetime.datetime(2050, 2, 1, tzinfo=UTC),
            end_date=datetime.datetime(2050, 2, 14, tzinfo=UTC),
        )
        with freeze_time("2050-01-01", tz_offset=0):
            self.assertFalse(contest.has_ended)
        with freeze_time("2050-02-01", tz_offset=0):
            self.assertFalse(contest.has_ended)
        with freeze_time("2050-02-15", tz_offset=0):
            self.assertTrue(contest.has_ended)
        self.assertEqual(
            contest.create_table_url,
            r"https://hanab.live/create-table?name=%21seed+otis1"
            r"&variantName=Duck+%285+Suits%29"
            r"&timed=true&timeBase=180&timePerTurn=30",
        )
        self.assertEqual(
            contest.hanab_stats_page_url, "https://hanab.live/seed/p3v55sotis1"
        )
        self.assertEqual(contest.max_score, 25)

        replay = HanabiReplayFactory.create(contest=contest, game_score=23)
        self.assertAlmostEqual(replay.get_base_spades(), 2.86557184)


class HanabiViewTests(EvanTestCase):
    def test_contest_list(self) -> None:
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
            resp = self.assertGet20X("hanabi-contests")
            self.assertContains(resp, "Candy Corn Mix", count=2)
            self.assertContains(resp, "Valentine Mix", count=1)
            self.assertNotContains(resp, "Holiday Mix")

    def test_register(self) -> None:
        verified_group = GroupFactory(name="Verified")
        UserFactory.create(username="mallory")
        UserFactory.create(username="alice", groups=(verified_group,))

        self.login("mallory")
        self.assertGet40X("hanabi-register")
        self.assertPost40X("hanabi-register", data={"hanab_username": "mallory"})

        self.login("alice")
        resp = self.assertGet20X("hanabi-register")
        self.assertNotContains(resp, "You already registered")
        resp = self.assertPost20X(
            "hanabi-register", data={"hanab_username": "alice"}, follow=True
        )
        self.assertContains(resp, "You set your username to alice.")
        self.assertTrue(
            HanabiPlayer.objects.filter(
                user__username="alice", hanab_username="alice"
            ).exists()
        )

        resp = self.assertGet20X("hanabi-register", follow=True)
        self.assertContains(resp, "You already registered")
        resp = self.assertPost20X(
            "hanabi-register", data={"hanab_username": "alice"}, follow=True
        )
        self.assertContains(resp, "You already registered")
