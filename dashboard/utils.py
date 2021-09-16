from datetime import datetime
from typing import List, Optional

from core.models import Unit
from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import QuerySet
from django.utils import timezone
from roster.models import Student

from dashboard.models import PSet


def pset_subquery(student: Student) -> Exists:
	return Exists(PSet.objects.filter(unit=OuterRef('pk'), student=student))


def unlocked_unit_ids(student: Student) -> List[int]:
	return list(student.unlocked_units.all().values_list('pk', flat=True))


def get_units_to_submit(student: Student) -> QuerySet[Unit]:
	queryset = student.unlocked_units.all()
	queryset = queryset.annotate(has_pset=pset_subquery(student))
	queryset = queryset.exclude(has_pset=True)
	return queryset


def get_units_to_unlock(student: Student) -> QuerySet[Unit]:
	queryset = student.curriculum.all()
	queryset = queryset.exclude(pk__in=unlocked_unit_ids(student))
	queryset = queryset.annotate(has_pset=pset_subquery(student))
	queryset = queryset.exclude(has_pset=True)
	return queryset


def get_days_since(t: Optional[datetime]) -> Optional[float]:
	if t is None:
		return None
	return (timezone.now() - t).total_seconds() / (3600 * 24)
