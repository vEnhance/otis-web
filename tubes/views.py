import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic.list import ListView

from otisweb.decorators import verified_required
from otisweb.mixins import VerifiedRequiredMixin

from .models import JoinRecord, Tube


class TubeList(VerifiedRequiredMixin, ListView[Tube]):
    model = Tube
    context_object_name = "tube_list"
    template_name = "tubes/tube_list.html"

    def get_queryset(self) -> QuerySet[Tube]:
        return Tube.objects.filter(status="TB_ACTIVE")


@verified_required
def tube_join(request: HttpRequest, pk: int) -> HttpResponse:
    tube = get_object_or_404(Tube, pk=pk)
    if not tube.status == "TB_ACTIVE" or not tube.accepting_signups:
        raise PermissionDenied("Cannot join right now")
    try:
        jr = JoinRecord.objects.get(tube=tube, user=request.user)
    except JoinRecord.DoesNotExist:
        jr = JoinRecord.objects.filter(tube=tube, user__isnull=True).first()
        if jr is None:
            # we ran out of valid codes to give fml
            messages.error(
                request, "Ran out of one-time invite codes, please contact staff."
            )
            logging.critical(
                request,
                f"{tube} somehow ran out of one-time codes when {request.user} tried to join",
            )

            return HttpResponseRedirect(reverse("tube-list"))
        else:
            jr.user = request.user
            jr.activation_time = timezone.now()
            jr.save()
    return HttpResponseRedirect(jr.invite_url if jr.invite_url else jr.tube.main_url)
