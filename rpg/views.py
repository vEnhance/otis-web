import logging
import random
from typing import Any

from braces.views import (  # NOQA
    LoginRequiredMixin,
    StaffuserRequiredMixin,
    SuperuserRequiredMixin,
)
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import Http404, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from sql_util.utils import Exists, SubqueryCount

from evans_django_tools import SUCCESS_LOG_LEVEL
from otisweb.mixins import VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest, get_days_since
from roster.models import Student
from roster.utils import get_student_by_pk, infer_student

from .forms import DiamondsForm
from .levelsys import LevelInfoDict, get_level_info, get_student_rows
from .models import Achievement, AchievementUnlock, Level, PalaceCarving

logger = logging.getLogger(__name__)


@login_required
def stats(request: AuthHttpRequest, student_pk: int) -> HttpResponse:
    student = get_student_by_pk(request, student_pk)
    unlocks = AchievementUnlock.objects.filter(user=student.user).order_by(
        "achievement__name"
    )
    unlocks = unlocks.select_related("achievement")
    context: dict[str, Any] = {
        "student": student,
        "form": DiamondsForm(),
        "achievements": unlocks,
    }
    if request.method == "POST":
        assert student.user is not None
        form = DiamondsForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]

            try:
                achievement = Achievement.objects.get(code__iexact=code)
            except Achievement.DoesNotExist:
                messages.error(request, "You entered an invalid code. 😭")
                logger.warn(
                    f"Invalid diamond code `{code}` from {student.name}",
                    extra={"request": request},
                )
            else:
                _, is_new = AchievementUnlock.objects.get_or_create(
                    user=student.user,
                    achievement=achievement,
                )
                if is_new is True:
                    msg = r"Achievement unlocked! 🎉 "
                    msg += f"You earned the achievement {achievement.name}."
                    if achievement.creator is not None:
                        msg += " This was a user-created achievement code, "
                        msg += "so please avoid sharing it with others."
                    messages.success(request, msg)
                    logger.log(
                        SUCCESS_LOG_LEVEL,
                        f"{student.name} just obtained `{achievement}`!",
                        extra={"request": request},
                    )
                else:
                    logger.info(
                        f"{student.name} has already obtained {achievement} before",
                        extra={"request": request},
                    )
                    messages.warning(
                        request,
                        r"Already unlocked! ❎ "
                        f"You already earned the achievement {achievement.name}.",
                    )

            form = DiamondsForm()
    else:
        form = DiamondsForm()
    try:
        context["first_achievement"] = Achievement.objects.get(pk=1)
    except Achievement.DoesNotExist:
        pass
    level_info = get_level_info(student)
    context |= level_info
    level_number = level_info["level_number"]
    obtained_levels = Level.objects.filter(threshold__lte=level_number).order_by(
        "-threshold"
    )
    context["obtained_levels"] = obtained_levels
    return render(request, "rpg/stats.html", context)


class AchievementList(LoginRequiredMixin, ListView[Achievement]):
    template_name = "rpg/diamond_list.html"

    def get_queryset(self) -> QuerySet[Achievement]:
        if not isinstance(self.request.user, User):
            raise PermissionDenied("Please log in")

        achievements = (
            Achievement.objects.all()
            .annotate(
                num_found=SubqueryCount("achievementunlock"),
                obtained=Exists(
                    Achievement.objects.filter(
                        pk=OuterRef("pk"), achievementunlock__user=self.request.user
                    )
                ),
            )
            .order_by("-obtained", "-num_found")
        )

        self.amount = len(achievements.filter(obtained=True))

        return achievements

    def get_context_data(self, **kwargs: dict[str, Any]):
        context = super().get_context_data(**kwargs)
        context["pk"] = self.request.user.pk
        try:
            context["student_pk"] = infer_student(self.request).pk
        except Http404:
            context["student_pk"] = None
        context["viewing"] = False
        return context


class AchievementDetail(VerifiedRequiredMixin, DetailView[Achievement]):
    template_name = "rpg/diamond_solution.html"
    model = Achievement
    context_object_name = "achievement"

    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponseBase:
        achievement = self.get_object()
        ret = super().dispatch(*args, **kwargs)  # trigger verified required
        if not isinstance(self.request.user, User):
            raise PermissionDenied("Log in first")
        elif self.request.user == achievement.creator:
            return ret
        elif self.request.user.is_superuser:
            messages.warning(self.request, "Viewing as admin…")
            return ret
        else:
            if not AchievementUnlock.objects.filter(
                user=self.request.user, achievement=achievement
            ).exists():
                raise PermissionDenied("You haven't found this one yet.")
            elif not achievement.show_solution:
                raise PermissionDenied(
                    "The solution page to this diamond is not public."
                )
            else:
                return ret


class FoundList(
    LoginRequiredMixin, StaffuserRequiredMixin, ListView[AchievementUnlock]
):
    raise_exception = True
    template_name = "rpg/found_list.html"
    context_object_name = "unlocks_list"

    def get_queryset(self) -> QuerySet[AchievementUnlock]:
        self.achievement = get_object_or_404(Achievement, pk=self.kwargs["pk"])
        return (
            AchievementUnlock.objects.filter(
                achievement=self.achievement,
            )
            .select_related("user")
            .order_by("-timestamp")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["achievement"] = self.achievement
        return context


@staff_member_required
def leaderboard(request: AuthHttpRequest) -> HttpResponse:
    students = Student.objects.filter(semester__active=True)
    rows = get_student_rows(students)
    rows.sort(
        key=lambda row: (
            -row["level"],
            -row["clubs"],
            -row["hearts"],
            -row["spades"],
            -row["diamonds"],
            row["student"].name.upper(),
        )
    )
    for row in rows:
        row["days_since_last_seen"] = get_days_since(row["last_seen"])
    context: dict[str, Any] = {"rows": rows}
    return render(request, "rpg/leaderboard.html", context)


def assert_maxed_out_level_info(student: Student) -> LevelInfoDict:
    level_info = get_level_info(student)
    if not level_info["is_maxed"]:
        raise PermissionDenied("Insufficient level")
    return level_info


class PalaceList(LoginRequiredMixin, ListView[PalaceCarving]):
    model = PalaceCarving
    context_object_name = "palace_carvings"
    template_name = "rpg/palace.html"

    def get_queryset(self):
        student = get_student_by_pk(self.request, self.kwargs["student_pk"])
        assert_maxed_out_level_info(student)
        self.student = student
        queryset = PalaceCarving.objects.filter(visible=True)
        queryset = queryset.exclude(display_name="")
        queryset = queryset.order_by("created_at")
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context


class AdminPalaceList(SuperuserRequiredMixin, ListView[PalaceCarving]):
    model = PalaceCarving
    context_object_name = "palace_carvings"
    template_name = "rpg/palace.html"

    def get_queryset(self):
        queryset = PalaceCarving.objects.filter(visible=True)
        queryset = queryset.exclude(display_name="")
        queryset = queryset.order_by("created_at")
        return queryset


class PalaceUpdate(
    LoginRequiredMixin,
    SuccessMessageMixin,
    UpdateView[PalaceCarving, BaseModelForm[PalaceCarving]],
):
    model = PalaceCarving
    fields = (
        "display_name",
        "hyperlink",
        "message",
        "visible",
        "image",
    )
    template_name = "rpg/palace_form.html"
    success_message = "Edited palace carving successfully!"

    def get_object(self, *args: Any, **kwargs: Any) -> PalaceCarving:
        student = get_student_by_pk(self.request, self.kwargs["student_pk"])
        assert_maxed_out_level_info(student)
        self.student = student
        carving, is_created = PalaceCarving.objects.get_or_create(user=student.user)
        if is_created is True:
            carving.display_name = student.name
        return carving

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context

    def get_success_url(self):
        return reverse("palace-list", args=(self.student.pk,))


class DiamondUpdate(
    LoginRequiredMixin,
    UpdateView[Achievement, BaseModelForm[Achievement]],
):
    model = Achievement
    fields = (
        "code",
        "name",
        "image",
        "description",
        "solution",
        "show_solution",
        "always_show_image",
    )
    success_message = "Updated diamond successfully."

    def get_object(self, *args: Any, **kwargs: Any) -> Achievement:
        student = get_student_by_pk(self.request, self.kwargs["student_pk"])
        level_info = assert_maxed_out_level_info(student)
        self.student = student

        achievement, is_new = Achievement.objects.get_or_create(creator=student.user)
        if is_new is True:
            achievement.code = "".join(
                random.choice("0123456789abcdef") for _ in range(24)
            )
            achievement.diamonds = min(level_info["meters"]["diamonds"].level, 7)
            achievement.name = student.name
            achievement.save()
        return achievement

    def form_valid(self, form: BaseModelForm[Achievement]):
        assert_maxed_out_level_info(self.student)
        n = 4
        form.instance.diamonds = n
        form.instance.creator = self.student.user
        messages.success(self.request, f"Successfully forged diamond worth {n}♦.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context

    def get_success_url(self):
        return reverse("diamond-update", args=(self.student.pk,))
