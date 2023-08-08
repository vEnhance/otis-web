from datetime import timedelta
from typing import TypedDict

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import QuerySet
from django.utils import timezone

from core.models import Unit, UserProfile
from dashboard.models import PSet, SemesterDownloadFile
from hanabi.models import HanabiContest
from markets.models import Market
from opal.models import OpalHunt
from otisweb.utils import MailChimpDatum, get_mailchimp_campaigns
from roster.models import Student


def pset_subquery(student: Student) -> Exists:
    return Exists(PSet.objects.filter(unit=OuterRef("pk"), student=student))


def unlocked_unit_pks(student: Student) -> list[int]:
    return list(student.unlocked_units.all().values_list("pk", flat=True))


def get_units_to_submit(student: Student) -> QuerySet[Unit]:
    queryset = student.unlocked_units.all()
    queryset = queryset.annotate(has_pset=pset_subquery(student))
    queryset = queryset.exclude(has_pset=True)
    return queryset


def get_units_to_unlock(student: Student) -> QuerySet[Unit]:
    queryset = student.curriculum.all()
    queryset = queryset.exclude(pk__in=unlocked_unit_pks(student))
    queryset = queryset.annotate(has_pset=pset_subquery(student))
    queryset = queryset.exclude(has_pset=True)
    return queryset


class NewsDict(TypedDict):
    emails: list[MailChimpDatum]
    downloads: QuerySet[SemesterDownloadFile]
    markets: QuerySet[Market]
    hanabis: QuerySet[HanabiContest]
    opals: QuerySet[OpalHunt]


def get_news(profile: UserProfile) -> NewsDict:
    return {
        "emails": [
            e
            for e in get_mailchimp_campaigns(14)
            if e["timestamp"] >= profile.last_notif_dismiss
        ],
        "downloads": SemesterDownloadFile.objects.filter(
            semester__active=True,
            created_at__gte=profile.last_notif_dismiss,
        ).filter(
            created_at__gte=timezone.now() - timedelta(days=14),
        ),
        "markets": Market.active.filter(
            start_date__gte=profile.last_notif_dismiss,
        ),
        "hanabis": HanabiContest.active.filter(
            start_date__gte=profile.last_notif_dismiss,
        ),
        "opals": OpalHunt.live.filter(
            start_date__gte=profile.last_notif_dismiss,
        ),
    }
