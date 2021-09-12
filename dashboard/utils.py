from typing import List

from core.models import Unit
from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import QuerySet
from roster.models import Student

from dashboard.models import PSet


def pset_subquery(student: Student) -> Exists:
	return Exists(PSet.objects.filter(unit=OuterRef('pk'), student=student))


def unlocked_unit_ids(student: Student) -> List[int]:
	return student.unlocked_units.all().values_list('pk', flat=True)


def get_units_to_submit(student: Student) -> QuerySet[Unit]:
	return student.unlocked_units.all().annotate(
		has_pset=pset_subquery(student),
	).exclude(has_pset=True)


def get_units_to_unlock(student: Student) -> QuerySet[Unit]:
	return student.curriculum.all().exclude(
		pk__in=unlocked_unit_ids(student),
	).annotate(has_pset=pset_subquery(student)).exclude(has_pset=True)
