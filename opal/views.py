from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.query import QuerySet
from django.views.generic.list import ListView

from .models import OpalHunt


class HuntList(LoginRequiredMixin, ListView[OpalHunt]):
    model = OpalHunt
    context_object_name = "hunts"

    def get_queryset(self) -> QuerySet[OpalHunt]:
        return OpalHunt.objects.all().order_by("-start_date")
