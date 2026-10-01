import datetime
from typing import Any

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpRequest
from django.test import RequestFactory
from freezegun import freeze_time

from core.factories import GroupFactory, UserFactory, UserProfileFactory
from dashboard.admin import AnnouncementAdmin
from dashboard.factories import AnnouncementFactory, SemesterDownloadFileFactory
from dashboard.models import Announcement
from dashboard.utils import get_news
from hanabi.factories import HanabiContestFactory
from markets.factories import MarketFactory
from opal.factories import OpalHuntFactory
from roster.factories import StudentFactory
from roster.models import Student
from surveys.factories import SurveyCompletionFactory, SurveyFactory


def at(day: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(day).replace(tzinfo=datetime.UTC)


def news(student: Student, dismissed: str, now: str) -> dict[str, list[Any]]:
    profile = UserProfileFactory.create(
        user=student.user, last_notif_dismiss=at(dismissed)
    )
    with freeze_time(now, tz_offset=0):
        return {key: list(qs) for key, qs in get_news(profile, student).items()}


SHOWN_UNTIL_STALE = [
    ("2021-06-01", "2021-07-01", True),
    ("2021-06-01", "2021-07-30", False),
    ("2021-07-02", "2021-07-02", False),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("dismissed", "now", "shown"), SHOWN_UNTIL_STALE)
def test_news_announcements(dismissed: str, now: str, shown: bool) -> None:
    with freeze_time("2021-06-30", tz_offset=0):
        announcement = AnnouncementFactory.create()
    items = news(StudentFactory.create(), dismissed, now)["announcements"]
    assert items == ([announcement] if shown else [])


@pytest.mark.django_db
@pytest.mark.parametrize(("dismissed", "now", "shown"), SHOWN_UNTIL_STALE)
def test_news_downloads(dismissed: str, now: str, shown: bool) -> None:
    alice = StudentFactory.create()
    with freeze_time("2021-06-30", tz_offset=0):
        download = SemesterDownloadFileFactory.create(semester=alice.semester)
    assert news(alice, dismissed, now)["downloads"] == ([download] if shown else [])


@pytest.mark.django_db
def test_news_downloads_only_from_own_semester() -> None:
    with freeze_time("2021-06-30", tz_offset=0):
        SemesterDownloadFileFactory.create()
    assert news(StudentFactory.create(), "2021-06-01", "2021-07-01")["downloads"] == []


WHILE_RUNNING = [
    ("2021-06-01", "2021-07-01", True),
    ("2021-06-01", "2021-07-30", False),
    ("2021-07-02", "2021-07-02", False),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("dismissed", "now", "shown"), WHILE_RUNNING)
def test_news_markets(dismissed: str, now: str, shown: bool) -> None:
    market = MarketFactory.create(
        start_date=at("2021-06-30"), end_date=at("2021-07-20")
    )
    items = news(StudentFactory.create(), dismissed, now)["markets"]
    assert items == ([market] if shown else [])


@pytest.mark.django_db
@pytest.mark.parametrize(("dismissed", "now", "shown"), WHILE_RUNNING)
def test_news_hanabi_contests(dismissed: str, now: str, shown: bool) -> None:
    contest = HanabiContestFactory.create(
        start_date=at("2021-06-30"), end_date=at("2021-07-25")
    )
    items = news(StudentFactory.create(), dismissed, now)["hanabis"]
    assert items == ([contest] if shown else [])


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("active", "dismissed", "now", "shown"),
    [
        (True, "2021-06-01", "2021-07-30", True),
        (False, "2021-06-01", "2021-07-01", False),
        (True, "2021-07-02", "2021-07-02", False),
        (True, "2021-06-01", "2022-07-02", False),
    ],
)
def test_news_opal_hunts(active: bool, dismissed: str, now: str, shown: bool) -> None:
    hunt = OpalHuntFactory.create(start_date=at("2021-06-30"), active=active)
    items = news(StudentFactory.create(), dismissed, now)["opals"]
    assert items == ([hunt] if shown else [])


@pytest.mark.django_db
@pytest.mark.parametrize(("dismissed", "now", "shown"), WHILE_RUNNING)
def test_news_surveys(dismissed: str, now: str, shown: bool) -> None:
    alice = StudentFactory.create()
    survey = SurveyFactory.create(
        semester=alice.semester,
        opens_at=at("2021-06-30"),
        closes_at=at("2021-07-20"),
    )
    assert news(alice, dismissed, now)["surveys"] == ([survey] if shown else [])


@pytest.mark.django_db
def test_news_skips_completed_survey() -> None:
    alice = StudentFactory.create()
    SurveyCompletionFactory.create(
        student=alice,
        survey=SurveyFactory.create(
            semester=alice.semester,
            opens_at=at("2021-06-30"),
            closes_at=at("2021-07-20"),
        ),
    )
    assert news(alice, "2021-06-01", "2021-07-01")["surveys"] == []


@pytest.mark.django_db
def test_news_skips_other_semesters_survey() -> None:
    SurveyFactory.create(opens_at=at("2021-06-30"), closes_at=at("2021-07-20"))
    assert news(StudentFactory.create(), "2021-06-01", "2021-07-01")["surveys"] == []


def verified_user():
    return UserFactory.create(groups=(GroupFactory(name="Verified"),))


@pytest.mark.django_db
def test_announcements_require_verified(otis) -> None:
    AnnouncementFactory.create(slug="one")
    otis.login(UserFactory.create())
    otis.get_40x("announcement-list")
    otis.get_40x("announcement-detail", "one")


@pytest.mark.django_db
def test_announcement_detail(otis) -> None:
    announcement = AnnouncementFactory.create(slug="one", content="하나")
    AnnouncementFactory.create(slug="two", content="둘")
    otis.login(verified_user())
    resp = otis.get_20x("announcement-detail", "one")
    assert resp.context["announcement"] == announcement


@pytest.fixture
def announcement_admin_request() -> HttpRequest:
    request = RequestFactory().get("/")
    request._messages = CookieStorage(request)  # type: ignore
    return request


@pytest.mark.django_db
def test_announcement_list_without_archive(otis) -> None:
    announcements = set(AnnouncementFactory.create_batch(2))
    otis.login(verified_user())
    resp = otis.get_20x("announcement-list")
    assert set(resp.context["current_announcements"]) == announcements
    assert list(resp.context["archived_announcements"]) == []


@pytest.mark.django_db
def test_archive_announcements(otis, announcement_admin_request) -> None:
    current = AnnouncementFactory.create(slug="current")
    stale = AnnouncementFactory.create(slug="stale")
    AnnouncementAdmin(Announcement, AdminSite()).archive_announcements(
        announcement_admin_request, Announcement.objects.filter(slug="stale")
    )
    stale.refresh_from_db()
    current.refresh_from_db()
    assert stale.archived is True
    assert current.archived is False

    otis.login(verified_user())
    resp = otis.get_20x("announcement-list")
    assert list(resp.context["current_announcements"]) == [current]
    assert list(resp.context["archived_announcements"]) == [stale]


@pytest.mark.django_db
def test_unarchive_announcements(announcement_admin_request) -> None:
    stale = AnnouncementFactory.create(slug="stale", archived=True)
    AnnouncementAdmin(Announcement, AdminSite()).unarchive_announcements(
        announcement_admin_request, Announcement.objects.filter(slug="stale")
    )
    stale.refresh_from_db()
    assert stale.archived is False
