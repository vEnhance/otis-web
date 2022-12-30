from typing import List

from core.models import Unit
from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import QuerySet
from roster.models import Student

from dashboard.models import PSet


def pset_subquery(student: Student) -> Exists:
    return Exists(PSet.objects.filter(unit=OuterRef("pk"), student=student))


def unlocked_unit_pks(student: Student) -> List[int]:
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
