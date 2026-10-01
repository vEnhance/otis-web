import datetime
import zoneinfo
from typing import Any

import pytest
from django.template import Context, Template
from django.utils import timezone

from core.factories import UserFactory
from core.templatetags.otis_extras import standing_row_class
from roster.factories import StudentFactory
from roster.models import StudentStanding


def render_timestamp(value: Any, args: str) -> str:
    template = Template("{% load otis_extras %}{% timestamp value " + args + " %}")
    return template.render(Context({"value": value})).strip()


def test_timestamp_tag_follows_active_timezone():
    value = datetime.datetime(2026, 9, 12, 23, 30, tzinfo=datetime.UTC)
    with timezone.override(zoneinfo.ZoneInfo("America/New_York")):
        eastern = render_timestamp(value, '"time"')
    with timezone.override(zoneinfo.ZoneInfo("Asia/Manila")):
        manila = render_timestamp(value, '"time"')

    assert ">12 Sep 2026 19:30:00 EDT</time>" in eastern
    assert ">13 Sep 2026 07:30:00 PST</time>" in manila
    assert 'datetime="2026-09-12T19:30:00-04:00"' in eastern
    assert 'datetime="2026-09-13T07:30:00+08:00"' in manila


@pytest.mark.parametrize(
    ("style", "text"),
    [
        ("date", "12 Sep 2026"),
        ("isodate", "2026-09-12"),
        ("time", "12 Sep 2026 19:30:00 EDT"),
        ("isotime", "2026-09-12 19:30 EDT"),
    ],
)
def test_timestamp_tag_styles(style: str, text: str):
    value = datetime.datetime(2026, 9, 12, 23, 30, tzinfo=datetime.UTC)
    with timezone.override(zoneinfo.ZoneInfo("America/New_York")):
        rendered = render_timestamp(value, f'"{style}"')
    assert f">{text}</time>" in rendered
    assert 'title="Sat, 12 Sep 2026 19:30:00 -0400"' in rendered


def test_timestamp_tag_on_plain_dates_and_none():
    rendered = render_timestamp(datetime.date(2026, 9, 12), '"time"')
    assert rendered == '<time datetime="2026-09-12">12 Sep 2026</time>'
    assert render_timestamp(datetime.date(2026, 9, 12), '"isotime"') == (
        '<time datetime="2026-09-12">2026-09-12</time>'
    )
    assert render_timestamp(None, '"date" default="(never)"') == "(never)"
    assert render_timestamp(None, '"date"') == ""


def test_timestamp_tag_relative():
    value = timezone.now() - datetime.timedelta(hours=3)
    rendered = render_timestamp(value, '"relative"')
    assert ">3\xa0hours ago</time>" in rendered
    assert "title=" in rendered


def test_timestamp_tag_rejects_unknown_style():
    with pytest.raises(ValueError):
        render_timestamp(timezone.now(), '"DATE_FORMAT"')


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("standing", "staff_class", "student_class"),
    [
        (StudentStanding.GOOD, "", ""),
        (StudentStanding.NEWBORN, "table-success", "table-success"),
        (StudentStanding.PROBATION, "table-warning", ""),
        (StudentStanding.SUSPENDED, "table-danger", "table-danger"),
        (StudentStanding.FAKE, "table-primary", "table-primary"),
        (StudentStanding.DROPPED, "table-info", "table-info"),
    ],
)
def test_standing_row_class(
    standing: StudentStanding, staff_class: str, student_class: str
) -> None:
    student = StudentFactory.create(standing=standing)
    assert standing_row_class(student, UserFactory.create(is_staff=True)) == staff_class
    assert standing_row_class(student, UserFactory.create()) == student_class
