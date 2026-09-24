# Functions to compute student levels and whatnot
import datetime
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any, TypedDict

from django.contrib.auth.models import User
from django.db.models.aggregates import Count, Max, Sum
from django.db.models.expressions import (
    Combinable,
    F,
    Func,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.fields import FloatField
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.utils import timezone
from django_discordo import VERBOSE_LOG_LEVEL
from sql_util.aggregates import SubqueryCount, SubquerySum
from sql_util.utils import Exists

from core.models import UserProfile
from core.utils import find_profile
from dashboard.models import PSet
from exams.models import ExamAttempt, MockCompleted
from hanabi.models import HanabiReplay
from markets.models import Guess
from payments.models import Job
from ponzi.models import PonziInvestment
from roster.models import Student
from suggestions.models import ProblemSuggestion

from .models import (
    AchievementUnlock,
    BonusLevel,
    BonusLevelUnlock,
    Level,
    QuestComplete,
)

BONUS_D_UNIT = 0.3
BONUS_Z_UNIT = 0.5

SuggestUnitSet = set[tuple[int, str, str]]

logger = logging.getLogger(__name__)


class Meter:
    def __init__(
        self,
        name: str,
        emoji: str,
        value: float,
        unit: str,
        color: str,
        max_value: int,
        dynamic_progress: bool = False,
    ):
        self.name = name
        self.emoji = emoji
        self.value = value
        self.unit = unit
        self.color = color
        self.max_value = max_value
        self.dynamic_progress = dynamic_progress

    @property
    def level(self) -> int:
        return int(max(0, self.value) ** 0.5)

    @property
    def im_level(self) -> int:
        return int(max(0, -self.value) ** 0.5)

    @property
    def str_level(self) -> str | None:
        if self.value >= 0:
            return str(self.level)
        x = int((-self.value) ** 0.5)
        if x == 1:
            return "i"
        else:
            return f"{x}i"

    @property
    def percent(self) -> int:
        eps = 0.4  # Make sure text fits in the bar
        if self.dynamic_progress:
            lvl = self.level
            prev_value = lvl**2
            current_gap = self.value - prev_value
            total_gap = 2 * lvl + 1
            k = (current_gap + eps * total_gap) / ((1 + eps) * total_gap)
        else:
            k = (self.value + eps * self.max_value) / ((1 + eps) * self.max_value)
        return max(1, min(100, int(100 * k)))

    @property
    def needed(self) -> float:
        return round((self.level + 1) ** 2 - self.value, 2)

    @property
    def thresh(self) -> int:
        return (self.level + 1) ** 2

    @property
    def total(self):
        return self.value

    @staticmethod
    def ClubMeter(value: int, dynamic_progress: bool):
        return Meter(
            name="Dexterity",
            emoji="♣️",
            value=value,
            unit="♣",
            color="#007bff;",
            max_value=2500,
            dynamic_progress=dynamic_progress,
        )

    @staticmethod
    def HeartMeter(value: float, dynamic_progress: bool):
        return Meter(
            name="Wisdom",
            emoji="🕰️",
            value=value,
            unit="♥",
            color="#198754",
            max_value=2500,
            dynamic_progress=dynamic_progress,
        )

    @staticmethod
    def SpadeMeter(value: float, dynamic_progress: bool):
        return Meter(
            name="Strength",
            emoji="🏆",
            value=value,
            unit="♠",
            color="#ae610f",
            max_value=169,
            dynamic_progress=dynamic_progress,
        )

    @staticmethod
    def DiamondMeter(value: int, dynamic_progress: bool):
        return Meter(
            name="Charisma",
            emoji="㊙️",
            value=value,
            unit="♦",
            color="#9c1421",
            max_value=144,
            dynamic_progress=dynamic_progress,
        )


AggregateDict = dict[str, int | float]


class FourMetersDict(TypedDict):
    spades: Meter
    clubs: Meter
    diamonds: Meter
    hearts: Meter


class LevelInfoDict(TypedDict):
    psets: QuerySet[PSet]
    pset_data: AggregateDict
    quiz_attempts: QuerySet[ExamAttempt]
    quest_completes: QuerySet[QuestComplete]
    meters: FourMetersDict
    level_number: int
    str_im_level: str
    level_name: str
    is_maxed: bool
    market_guesses: QuerySet[Guess]
    suggest_unit_set: SuggestUnitSet
    mock_completes: QuerySet[MockCompleted]
    completed_jobs: QuerySet[Job]
    bonus_levels: QuerySet[BonusLevel]
    hanabi_replays: QuerySet[HanabiReplay]
    ponzi_investments: QuerySet[PonziInvestment]


def get_level_info(student: Student) -> LevelInfoDict:
    """Uses a bunch of expensive database queries to compute a student's levels and data,
    returning the findings as a typed dictionary."""

    level_data = LevelInfoDict()  # type: ignore

    total_clubs, total_hearts = get_clubs_hearts_stats(student, level_data)

    total_diamonds = get_diamond_stats(student)

    total_spades = get_spade_stats(student.user, level_data)

    profile = find_profile(student.user)
    dynamic_progress = profile is not None and profile.dynamic_progress

    meters: FourMetersDict = {
        "clubs": Meter.ClubMeter(int(total_clubs), dynamic_progress),
        "hearts": Meter.HeartMeter(round(total_hearts, 2), dynamic_progress),
        "diamonds": Meter.DiamondMeter(int(total_diamonds), dynamic_progress),
        "spades": Meter.SpadeMeter(round(total_spades, 2), dynamic_progress),
    }

    # Real component of level
    level_number = sum(meter.level for meter in meters.values())  # type: ignore
    level = (
        Level.objects.filter(threshold__lte=level_number).order_by("-threshold").first()
    )
    level_name = level.name if level is not None else "No Level"
    max_level = Level.objects.all().aggregate(max=Max("threshold"))["max"] or 0

    # Imaginary component of level
    im_level_number = sum(meter.im_level for meter in meters.values())  # type: ignore
    if im_level_number == 0:
        str_im_level = ""
    elif im_level_number == 1:
        str_im_level = "+ i"
    else:
        str_im_level = f"+ {im_level_number}i"

    level_data["meters"] = meters
    level_data["level_number"] = level_number
    level_data["level_name"] = level_name
    level_data["is_maxed"] = level_number >= max_level
    level_data["bonus_levels"] = BonusLevel.objects.filter(level__lte=level_number)
    level_data["str_im_level"] = str_im_level

    return level_data


def get_clubs_hearts_stats(
    student: Student, leveldict: LevelInfoDict = None
) -> tuple[float, int]:
    psets = PSet.objects.filter(student__user=student.user, status="A", eligible=True)
    psets = psets.order_by("upload__created_at")
    pset_data = psets.aggregate(
        clubs_any=Sum("clubs"),
        clubs_D=Sum("clubs", filter=Q(unit__code__startswith="D")),
        clubs_Z=Sum("clubs", filter=Q(unit__code__startswith="Z")),
        hearts=Sum("hours"),
    )
    total_clubs: float = (
        (pset_data["clubs_any"] or 0)
        + (pset_data["clubs_D"] or 0) * BONUS_D_UNIT
        + (pset_data["clubs_Z"] or 0) * BONUS_Z_UNIT
    )
    total_hearts: int = pset_data["hearts"] or 0

    if leveldict is not None:
        leveldict["psets"] = psets
        leveldict["pset_data"] = pset_data

    return total_clubs, total_hearts


def get_diamond_stats(student: Student) -> int:
    diamond_qset = AchievementUnlock.objects.filter(user=student.user)
    total_diamonds = diamond_qset.aggregate(s=Sum("achievement__diamonds"))["s"] or 0

    return total_diamonds


UserRef = User | OuterRef


def quiz_attempts(user: UserRef) -> QuerySet[ExamAttempt]:
    return ExamAttempt.objects.filter(student__user=user)


def quest_completes(user: UserRef) -> QuerySet[QuestComplete]:
    return QuestComplete.objects.filter(student__user=user)


def mock_completes(user: UserRef) -> QuerySet[MockCompleted]:
    return MockCompleted.objects.filter(student__user=user)


def market_guesses(user: UserRef) -> QuerySet[Guess]:
    return Guess.objects.filter(user=user, market__end_date__lt=timezone.now())


def spade_suggestions(user: UserRef) -> QuerySet[ProblemSuggestion]:
    return ProblemSuggestion.objects.filter(
        user=user,
        status__in=("SUGG_NOK", "SUGG_OK"),
        eligible=True,
    )


def completed_jobs(user: UserRef) -> QuerySet[Job]:
    return Job.objects.filter(assignee__user=user, progress="JOB_VFD")


def hanabi_replays(user: UserRef) -> QuerySet[HanabiReplay]:
    return HanabiReplay.objects.filter(
        contest__processed=True,
        hanabiparticipation__player__user=user,
    )


def ponzi_investments(user: UserRef) -> QuerySet[PonziInvestment]:
    return PonziInvestment.objects.filter(user=user)


# Plain SQL functions rather than Sum/Count: Django adds a GROUP BY for real
# aggregates, and we want one row per subquery with no grouping at all.
class SQLAggregate(Func):
    def __init__(self, expression: Any):
        super().__init__(expression, output_field=FloatField())


class SQLSum(SQLAggregate):
    function = "SUM"


class SQLCountDistinct(SQLAggregate):
    function = "COUNT"
    template = "%(function)s(DISTINCT %(expressions)s)"


SPADE_SOURCES: tuple[tuple[Callable[[UserRef], QuerySet[Any]], Func], ...] = (
    (quiz_attempts, SQLSum(F("score") * 2)),
    (quest_completes, SQLSum("spades")),
    (mock_completes, SQLSum(Value(3))),
    (market_guesses, SQLSum("score")),
    (spade_suggestions, SQLCountDistinct("unit")),
    (completed_jobs, SQLSum("spades_bounty")),
    (hanabi_replays, SQLSum("spades_score")),
    (ponzi_investments, SQLSum(Coalesce("payout", Value(Decimal(0))) - F("amount"))),
)


def spades_expression(user: OuterRef) -> Combinable:
    total: Combinable = Value(0.0)
    for queryset, value in SPADE_SOURCES:
        subquery = Subquery(queryset(user).order_by().values(total=value))
        total += Coalesce(subquery, Value(0.0))
    return total


def get_spade_stats(user: User, leveldict: LevelInfoDict = None) -> float:
    if leveldict is not None:
        leveldict["quiz_attempts"] = quiz_attempts(user).order_by(
            "quiz__family", "quiz__number"
        )
        leveldict["quest_completes"] = quest_completes(user).order_by("-timestamp")
        leveldict["mock_completes"] = (
            mock_completes(user)
            .select_related("exam")
            .order_by("exam__family", "exam__number")
        )
        leveldict["market_guesses"] = (
            market_guesses(user).order_by("-market__end_date").select_related("market")
        )
        leveldict["suggest_unit_set"] = set(
            spade_suggestions(user).values_list(
                "unit__pk", "unit__group__name", "unit__code"
            )
        )
        leveldict["completed_jobs"] = completed_jobs(user).select_related("folder")
        leveldict["hanabi_replays"] = hanabi_replays(user)
        leveldict["ponzi_investments"] = ponzi_investments(user).select_related(
            "scheme"
        )

    spades = (
        User.objects.annotate(spades=spades_expression(OuterRef("pk")))
        .values_list("spades", flat=True)
        .get(pk=user.pk)
    )
    return float(spades)


def annotate_student_queryset_with_scores(
    queryset: QuerySet[Student],
) -> QuerySet[Student]:
    """Helper function for constructing large lists of students
    Selects all important information to prevent a bunch of SQL queries"""
    return queryset.select_related(
        "user", "user__profile", "assistant", "semester"
    ).annotate(
        num_psets=SubqueryCount("pset", filter=Q(status="A", eligible=True)),
        clubs_any=SubquerySum(
            "user__student__pset__clubs", filter=Q(status="A", eligible=True)
        ),
        clubs_D=SubquerySum(
            "user__student__pset__clubs",
            filter=Q(status="A", eligible=True, unit__code__startswith="D"),
        ),
        clubs_Z=SubquerySum(
            "user__student__pset__clubs",
            filter=Q(status="A", eligible=True, unit__code__startswith="Z"),
        ),
        hearts=SubquerySum(
            "user__student__pset__hours",
            filter=Q(status="A", eligible=True),
        ),
        diamonds=SubquerySum("user__achievementunlock__achievement__diamonds"),
        pset_B_count=SubqueryCount(
            "pset__pk",
            filter=Q(eligible=True, unit__code__startswith="B"),
        ),
        pset_D_count=SubqueryCount(
            "pset__pk",
            filter=Q(eligible=True, unit__code__startswith="D"),
        ),
        pset_Z_count=SubqueryCount(
            "pset__pk",
            filter=Q(eligible=True, unit__code__startswith="Z"),
        ),
        num_semesters=SubqueryCount("user__student"),
        spades=spades_expression(OuterRef("user")),
    )


def compute_insanity_rating(b: int, d: int, z: int) -> float:
    assert min(b, d, z) >= 0
    return 0 if b == 0 and d == 0 and z == 0 else (z - b) / (b + d + z)


def get_student_rows(queryset: QuerySet[Student]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    levels: dict[int, str] = {
        level.threshold: level.name for level in Level.objects.all()
    }
    if not levels:
        levels[0] = "No level"
    max_level = max(levels.keys())

    for student in annotate_student_queryset_with_scores(queryset):
        row: dict[str, Any] = {
            "student": student,
            "spades": float(getattr(student, "spades", 0) or 0),
        }
        row["hearts"] = getattr(student, "hearts", 0) or 0
        row["clubs"] = getattr(student, "clubs_any", 0) or 0
        row["clubs"] += BONUS_D_UNIT * (getattr(student, "clubs_D", 0) or 0)
        row["clubs"] += BONUS_Z_UNIT * (getattr(student, "clubs_Z", 0) or 0)
        row["diamonds"] = getattr(student, "diamonds", 0) or 0
        row["level"] = sum(
            int(max(row[k], 0) ** 0.5)
            for k in ("spades", "hearts", "clubs", "diamonds")
        )
        try:
            row["last_seen"] = student.user.profile.last_seen
        except UserProfile.DoesNotExist:
            row["last_seen"] = datetime.datetime.fromtimestamp(0, tz=datetime.UTC)
        row["insanity"] = compute_insanity_rating(
            student.pset_B_count,  # type: ignore
            student.pset_D_count,  # type: ignore
            student.pset_Z_count,  # type: ignore
        )
        if row["level"] > max_level:
            row["level_name"] = levels[max_level]
        else:
            row["level_name"] = levels.get(row["level"], "No level")
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row["student"].semester.pk,
            not row["student"].legit,
            row["student"].user.first_name,
            row["student"].user.last_name,
        )
    )
    return rows


def check_level_up(student: Student, level_info: LevelInfoDict) -> bool:
    if not student.semester.active:
        return False
    level_number = level_info["level_number"]
    if level_number <= student.last_level_seen:
        return False

    bonuses = BonusLevel.objects.filter(level__lte=level_number)
    bonuses = bonuses.annotate(
        gotten=Exists("bonuslevelunlock", filter=Q(student__user=student.user))
    )
    bonuses = bonuses.exclude(gotten=True)

    if bonuses.exists():
        psets = PSet.objects.filter(student=student)
        counts = psets.aggregate(
            b=Count("pk", unique=True, filter=Q(unit__code__startswith="B")),
            d=Count("pk", unique=True, filter=Q(unit__code__startswith="D")),
            z=Count("pk", unique=True, filter=Q(unit__code__startswith="Z")),
        )
        r = compute_insanity_rating(b=counts["b"], d=counts["d"], z=counts["z"])

        for bonus in bonuses:
            units = bonus.group.unit_set
            if r >= 0.5:
                unit = units.filter(code__startswith="Z").first()
            elif r <= -0.5:
                unit = units.filter(code__startswith="B").first()
            else:
                unit = units.filter(code__startswith="D").first()
            if unit is not None:
                student.curriculum.add(unit)
                BonusLevelUnlock.objects.create(bonus=bonus, student=student)
                logger.log(VERBOSE_LOG_LEVEL, f"{student} obtained special unit {unit}")

    student.last_level_seen = level_number
    student.save()
    return True
