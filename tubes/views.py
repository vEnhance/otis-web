from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls.base import reverse
from django.views.generic.list import ListView
from sql_util.aggregates import Exists

from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin

from .models import JoinRecord, Tube


class TubeList(VerifiedRequiredMixin, ListView[Tube]):
    model = Tube
    context_object_name = "tube_list"
    template_name = "tubes/tube_list.html"

    def get_queryset(self) -> QuerySet[Tube]:
        return Tube.objects.filter(status="TB_ACTIVE").annotate(
            joined=Exists("joinrecord", filter=Q(user=self.request.user))
        )


@verified_required
def tube_join(request: HttpRequest, pk: int) -> HttpResponse:
    tube = get_object_or_404(Tube, pk=pk)
    if not tube.is_active:
        raise PermissionDenied("Cannot join inactive tube")
    elif JoinRecord.objects.filter(tube=tube, user=request.user).exists():
        messages.error(request, "You already joined this.")
        return HttpResponseRedirect(reverse("tubes-list"))
    elif not tube.has_join_url:
        messages.error(request, "Joining is not currently possible.")
        return HttpResponseRedirect(reverse("tubes-list"))
    else:
        JoinRecord.objects.create(user=request.user, tube=tube)
        return HttpResponseRedirect(tube.join_url)
