import logging
import random
from typing import Any

from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models import F, OuterRef
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import Http404, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from django_discordo import SUCCESS_LOG_LEVEL
from sql_util.utils import Exists, SubqueryCount

from otisweb.decorators import staff_required
from otisweb.mixins import AdminRequiredMixin, StaffRequiredMixin, VerifiedRequiredMixin
from otisweb.utils import AuthHttpRequest, get_days_since
from roster.models import Student
from roster.utils import get_student_by_pk, infer_student
from rpg.models import VulnerabilityRecord

from .forms import DiamondsForm
from .levelsys import LevelInfoDict, get_level_info, get_student_rows
from .models import (
    GUESS_CODE_MAX_LENGTH,
    WRONG_GUESS_LIMIT,
    Achievement,
    AchievementCodeGuess,
    AchievementUnlock,
    Level,
    PalaceCarving,
    get_guess_rate_limit_release,
)

logger = logging.getLogger(__name__)

RUBY_PALACE_DIAMOND_VALUE = 1


def handle_diamond_guess(
    request: AuthHttpRequest, student: Student, code: str, is_well_formed: bool
) -> None:
    """Records a guess at a diamond code and awards the diamond if it was right.

    Guesses that aren't shaped like a code at all are recorded too, but are
    never looked up; the form has already told the user those were rejected.

    The rate limit is enforced against the user who submitted the guess, which
    is not necessarily the user the diamond would be awarded to (staff members
    can submit codes from a student's stats page).
    """
    assert student.user is not None
    release = get_guess_rate_limit_release(request.user)
    if release is not None:
        messages.error(
            request,
            f"🛑 You've used up your {WRONG_GUESS_LIMIT} incorrect guesses. "
            f"You can try again {naturaltime(release)}.",
        )
        return

    achievement = (
        Achievement.objects.exclude(code="").filter(code__iexact=code).first()
        if is_well_formed
        else None
    )
    AchievementCodeGuess.objects.create(
        user=request.user,
        code=code[:GUESS_CODE_MAX_LENGTH],
        achievement=achievement,
        is_correct=achievement is not None,
        is_well_formed=is_well_formed,
    )
    if achievement is None:
        if is_well_formed:
            messages.error(request, "❌ You entered an invalid code.")
        return

    is_first_obtain = (
        not AchievementUnlock.objects.filter(achievement=achievement)
        .exclude(achievement__creator=F("user"))
        .exists()
    ) and not achievement.creator == student.user
    _, is_new = AchievementUnlock.objects.get_or_create(
        user=student.user,
        achievement=achievement,
        defaults={"is_first_obtain": is_first_obtain},
    )
    if is_new is True:
        msg = r"🎉 Achievement unlocked! "
        if is_first_obtain:
            logger.log(
                SUCCESS_LOG_LEVEL,
                f"`{achievement}` newly found by {student.name}! Wow!",
                extra={"request": request},
            )
            msg += f"You're the first to find {achievement.name}! Wowie!"
        else:
            logger.info(
                f"{student.name} just obtained `{achievement}`!",
                extra={"request": request},
            )
            msg += f"You earned the achievement {achievement.name}."
        if achievement.creator is not None:
            msg += " This was a user-created achievement code, "
            msg += "so please avoid sharing it with others."
        messages.success(request, msg)
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
        form = DiamondsForm(request.POST)
        is_well_formed = form.is_valid()
        if is_well_formed:
            code = form.cleaned_data["code"]
        else:
            code = request.POST.get("code", "").strip()
        if code:
            handle_diamond_guess(request, student, code, is_well_formed)
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
    context["form"] = form
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

    def get_context_data(self, **kwargs: Any):
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


class FoundList(LoginRequiredMixin, StaffRequiredMixin, ListView[AchievementUnlock]):
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


@staff_required
def leaderboard(request: AuthHttpRequest) -> HttpResponse:
    students = Student.objects.filter(semester__active=True, enabled=True, legit=True)
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


class AdminPalaceList(AdminRequiredMixin, ListView[PalaceCarving]):
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
        logger.info(
            f"{student} {'created' if is_created else 'updated'} their carving in the Ruby Palace.",
        )
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
        "show_creator",
        "show_solution",
        "always_show_image",
    )
    success_message = "Updated diamond successfully."

    def get_object(self, *args: Any, **kwargs: Any) -> Achievement:
        student = get_student_by_pk(self.request, self.kwargs["student_pk"])
        assert_maxed_out_level_info(student)
        self.student = student

        achievement, is_new = Achievement.objects.get_or_create(creator=student.user)
        if is_new is True:
            achievement.code = "".join(
                random.choice("0123456789abcdef") for _ in range(24)
            )
            achievement.diamonds = RUBY_PALACE_DIAMOND_VALUE
            achievement.name = student.name
            achievement.save()

        logger.info(
            f"{student} {'forged' if is_new else 'updated'} their diamond in the Ruby Palace.",
        )
        return achievement

    def form_valid(self, form: BaseModelForm[Achievement]):
        form.instance.creator = self.student.user
        messages.success(self.request, "Successfully forged diamond.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.student
        return context

    def get_success_url(self):
        return reverse("diamond-update", args=(self.student.pk,))


class GithubLandingView(ListView[VulnerabilityRecord]):
    model = VulnerabilityRecord
    template_name = "rpg/github_landing.html"
    context_object_name = "vulnerabilities"
