# Functions to compute student levels and whatnot
import datetime
import logging
from typing import Any, Set, Tuple, TypedDict, Union

from django.db.models.aggregates import Count, Max, Sum
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.utils import timezone
from sql_util.aggregates import SubqueryCount, SubquerySum
from sql_util.utils import Exists

from core.models import UserProfile
from dashboard.models import PSet
from evans_django_tools import VERBOSE_LOG_LEVEL
from exams.models import ExamAttempt, MockCompleted
from hanabi.models import HanabiReplay
from markets.models import Guess
from payments.models import Job
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

SuggestUnitSet = Set[Tuple[int, str, str]]

logger = logging.getLogger(__name__)


class Meter:
    def __init__(
        self,
        name: str,
        emoji: str,
        value: Union[float, int],
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


AggregateDict = dict[str, Union[int, float]]


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


def get_week_count(dates: list[datetime.datetime]) -> int:
    seen: list[Tuple[int, int]] = []
    for d in dates:
        d = d.astimezone(tz=datetime.timezone.utc)
        week_number = d.isocalendar()[1]
        year = d.year
        seen.append((year, week_number))
    return len(set(seen))


def get_level_info(student: Student) -> LevelInfoDict:
    """Uses a bunch of expensive database queries to compute a student's levels and data,
    returning the findings as a typed dictionary."""

    level_data = LevelInfoDict()  # type: ignore

    total_clubs, total_hearts = get_clubs_hearts_stats(student, level_data)

    total_diamonds = get_diamond_stats(student)

    total_spades = get_spade_stats(student, level_data)

    try:
        dynamic_progress = (UserProfile.objects.get(user=student.user)).dynamic_progress
    except UserProfile.DoesNotExist:
        dynamic_progress = False

    meters: FourMetersDict = {
        "clubs": Meter.ClubMeter(int(total_clubs), dynamic_progress),
        "hearts": Meter.HeartMeter(round(total_hearts, 2), dynamic_progress),
        "diamonds": Meter.DiamondMeter(int(total_diamonds), dynamic_progress),
        "spades": Meter.SpadeMeter(round(total_spades, 1), dynamic_progress),
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
) -> Tuple[float, int]:
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


def get_spade_stats(student: Student, leveldict: LevelInfoDict = None) -> int:
    total_spades = 0

    # a billion unrelated spades items lol
    quiz_attempts = ExamAttempt.objects.filter(student__user=student.user)
    quiz_attempts = quiz_attempts.order_by("quiz__family", "quiz__number")
    total_spades = (quiz_attempts.aggregate(total=Sum("score"))["total"] or 0) * 2

    quest_completes = QuestComplete.objects.filter(student__user=student.user)
    quest_completes = quest_completes.order_by("-timestamp")
    total_spades += quest_completes.aggregate(total=Sum("spades"))["total"] or 0

    mock_completes = MockCompleted.objects.filter(student__user=student.user)
    mock_completes = mock_completes.select_related("exam")
    mock_completes = mock_completes.order_by("exam__family", "exam__number")
    total_spades += mock_completes.count() * 3

    market_guesses = (
        Guess.objects.filter(
            user=student.user,
            market__end_date__lt=timezone.now(),
        )
        .order_by("-market__end_date")
        .select_related("market")
    )
    total_spades += market_guesses.aggregate(total=Sum("score"))["total"] or 0

    suggested_units_queryset = ProblemSuggestion.objects.filter(
        user=student.user,
        status__in=("SUGG_NOK", "SUGG_OK"),
        eligible=True,
    ).values_list(
        "unit__pk",
        "unit__group__name",
        "unit__code",
    )
    suggest_units_set: SuggestUnitSet = set(suggested_units_queryset)
    total_spades += len(suggest_units_set)

    completed_jobs = Job.objects.filter(
        assignee__user=student.user, progress="JOB_VFD"
    ).select_related("folder")
    total_spades += completed_jobs.aggregate(total=Sum("spades_bounty"))["total"] or 0

    hanabi_replays = HanabiReplay.objects.filter(
        contest__processed=True,
        hanabiparticipation__player__user=student.user,
    )
    total_spades += hanabi_replays.aggregate(total=Sum("spades_score"))["total"] or 0

    if leveldict is not None:
        leveldict["quiz_attempts"] = quiz_attempts
        leveldict["quest_completes"] = quest_completes
        leveldict["market_guesses"] = market_guesses
        leveldict["mock_completes"] = mock_completes
        leveldict["suggest_unit_set"] = suggest_units_set
        leveldict["completed_jobs"] = completed_jobs
        leveldict["hanabi_replays"] = hanabi_replays

    return total_spades


def annotate_student_queryset_with_scores(
    queryset: QuerySet[Student],
) -> QuerySet[Student]:
    """Helper function for constructing large lists of students
    Selects all important information to prevent a bunch of SQL queries"""
    guess_subquery = (
        Guess.objects.filter(
            user=OuterRef("user"),
            market__end_date__lt=timezone.now(),
        )
        .order_by()
        .values("user")
        .annotate(total=Sum("score"))
        .values("total")
    )

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
        spades_quizzes=SubquerySum("user__student__examattempt__score"),
        spades_quests=SubquerySum("user__student__questcomplete__spades"),
        spades_markets=Subquery(guess_subquery),  # type: ignore
        spades_count_mocks=SubqueryCount("user__student__mockcompleted"),
        spades_suggestions=SubqueryCount(
            "user__problemsuggestion__unit__pk",
            filter=Q(status__in=("SUGG_NOK", "SUGG_OK"), eligible=True),
        ),
        spades_jobs=SubquerySum(
            "user__workers__job__spades_bounty",
            filter=Q(progress="JOB_VFD"),
        ),
        spades_hanabi=SubquerySum(
            "user__hanabiplayer__hanabiparticipation__replay__spades_score",
            filter=Q(contest__processed=True),
        ),
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
            "spades": (getattr(student, "spades_quizzes", 0) or 0) * 2,
        }
        row["spades"] += getattr(student, "spades_quests", 0) or 0
        row["spades"] += (getattr(student, "spades_count_mocks", 0) or 0) * 3
        row["spades"] += getattr(student, "spades_suggestions", 0) or 0
        row["spades"] += getattr(student, "spades_markets", 0) or 0
        row["spades"] += getattr(student, "spades_jobs", 0) or 0
        row["spades"] += getattr(student, "spades_hanabi", 0) or 0
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
            row["last_seen"] = datetime.datetime.fromtimestamp(
                0, tz=datetime.timezone.utc
            )
        row["insanity"] = compute_insanity_rating(
            getattr(student, "pset_B_count"),
            getattr(student, "pset_D_count"),
            getattr(student, "pset_Z_count"),
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
