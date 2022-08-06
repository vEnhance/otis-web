# Functions to compute student levels and whatnot
import logging
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple, TypedDict, Union

from arch.models import Hint
from core.models import UserProfile
from django.db.models.aggregates import Count, Max, Sum
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.utils import timezone
from dwhandler import SUCCESS_LOG_LEVEL
from exams.models import ExamAttempt, MockCompleted
from markets.models import Guess
from reversion.models import Version
from roster.models import Student
from sql_util.aggregates import SubqueryCount, SubquerySum
from sql_util.utils import Exists

from dashboard.models import AchievementUnlock, BonusLevel, BonusLevelUnlock, Level, ProblemSuggestion, PSet, QuestComplete  # NOQA

BONUS_D_UNIT = 0.3
BONUS_Z_UNIT = 0.5

SuggestUnitSet = Set[Tuple[int, str, str]]

logger = logging.getLogger(__name__)


class Meter:
	def __init__(
		self,
		name: str,
		emoji: str,
		value: int,
		unit: str,
		color: str,
		max_value: int,
	):
		self.name = name
		self.emoji = emoji
		self.value = value
		self.unit = unit
		self.color = color
		self.max_value = max_value

	@property
	def level(self) -> int:
		return int(max(0, self.value)**0.5)

	@property
	def percent(self) -> int:
		eps = 0.25
		k = (self.value + eps * self.max_value) / ((1 + eps) * self.max_value)
		return min(100, int(100 * k))

	@property
	def needed(self) -> int:
		return (self.level + 1)**2 - self.value

	@property
	def thresh(self) -> int:
		return (self.level + 1)**2

	@property
	def total(self):
		return self.value

	@staticmethod
	def ClubMeter(value: int):
		return Meter(
			name="Dexterity", emoji="♣️", value=value, unit="♣", color='#007bff;', max_value=2500
		)

	@staticmethod
	def HeartMeter(value: int):
		return Meter(
			name="Wisdom", emoji="🕰️", value=value, unit="♥", color='#198754', max_value=2500
		)

	@staticmethod
	def SpadeMeter(value: int):
		return Meter(
			name="Strength", emoji="🏆", value=value, unit="♠", color='#ae610f', max_value=125
		)

	@staticmethod
	def DiamondMeter(value: int):
		return Meter(
			name="Charisma", emoji="㊙️", value=value, unit="◆", color='#9c1421', max_value=100
		)


AggregateDict = Dict[str, Union[int, float]]


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
	level_name: str
	is_maxed: bool
	market_guesses: QuerySet[Guess]
	hint_spades: int
	suggest_unit_set: SuggestUnitSet
	mock_completes: QuerySet[MockCompleted]


def get_week_count(dates: List[datetime]) -> int:
	seen: List[Tuple[int, int]] = []
	for d in dates:
		d = d.astimezone(tz=timezone.utc)
		week_number = d.isocalendar()[1]
		year = d.year
		seen.append((year, week_number))
	return len(set(seen))


def get_level_info(student: Student) -> LevelInfoDict:
	"""Uses a bunch of expensive database queries to compute a student's levels and data,
	returning the findings as a typed dictionary."""

	psets = PSet.objects.filter(student__user=student.user, approved=True, eligible=True)
	pset_data = psets.aggregate(
		clubs_any=Sum('clubs'),
		clubs_D=Sum('clubs', filter=Q(unit__code__startswith='D')),
		clubs_Z=Sum('clubs', filter=Q(unit__code__startswith='Z')),
		hearts=Sum('hours'),
	)
	total_clubs = (
		(pset_data['clubs_any'] or 0) + (pset_data['clubs_D'] or 0) * BONUS_D_UNIT +
		(pset_data['clubs_Z'] or 0) * BONUS_Z_UNIT
	)
	total_hearts = pset_data['hearts'] or 0

	total_diamonds = AchievementUnlock.objects.filter(user=student.user).aggregate(
		Sum('achievement__diamonds')
	)['achievement__diamonds__sum'] or 0

	quiz_attempts = ExamAttempt.objects.filter(student__user=student.user)
	quest_completes = QuestComplete.objects.filter(student__user=student.user)
	mock_completes = MockCompleted.objects.filter(student__user=student.user)
	mock_completes = mock_completes.select_related('exam')
	market_guesses = Guess.objects.filter(
		user=student.user,
		market__end_date__lt=timezone.now(),
	).select_related('market')
	suggested_units_queryset = ProblemSuggestion.objects.filter(
		user=student.user,
		resolved=True,
		eligible=True,
	).values_list(
		'unit__pk',
		'unit__group__name',
		'unit__code',
	)
	suggest_units_set: SuggestUnitSet = set(suggested_units_queryset)
	hints_written = Version.objects.get_for_model(Hint)  # type: ignore
	hints_written = hints_written.filter(revision__user_id=student.user.id)
	hints_written = hints_written.values_list('revision__date_created', flat=True)
	hint_spades = get_week_count(list(hints_written))

	total_spades = (quiz_attempts.aggregate(Sum('score'))['score__sum'] or 0) * 2
	total_spades += quest_completes.aggregate(Sum('spades'))['spades__sum'] or 0
	total_spades += market_guesses.aggregate(Sum('score'))['score__sum'] or 0
	total_spades += mock_completes.count() * 3
	total_spades += len(suggest_units_set)
	# TODO total_spades += hint_spades

	meters: FourMetersDict = {
		'clubs': Meter.ClubMeter(int(total_clubs)),
		'hearts': Meter.HeartMeter(int(total_hearts)),
		'diamonds': Meter.DiamondMeter(total_diamonds),
		'spades': Meter.SpadeMeter(int(total_spades)),
	}
	level_number = sum(meter.level for meter in meters.values())  # type: ignore
	level = Level.objects.filter(threshold__lte=level_number).order_by('-threshold').first()
	level_name = level.name if level is not None else 'No Level'
	max_level = Level.objects.all().aggregate(max=Max('threshold'))['max'] or 0
	level_data: LevelInfoDict = {
		'psets': psets,
		'pset_data': pset_data,
		'meters': meters,
		'level_number': level_number,
		'level_name': level_name,
		'is_maxed': level_number >= max_level,
		# spade properties
		'quiz_attempts': quiz_attempts,
		'quest_completes': quest_completes,
		'market_guesses': market_guesses,
		'mock_completes': mock_completes,
		'suggest_unit_set': suggest_units_set,
		'hint_spades': hint_spades,
	}
	return level_data


def annotate_student_queryset_with_scores(queryset: QuerySet[Student]) -> QuerySet[Student]:
	"""Helper function for constructing large lists of students
	Selects all important information to prevent a bunch of SQL queries"""
	guess_subquery = Guess.objects.filter(
		user=OuterRef('user'),
		market__end_date__lt=timezone.now(),
	).order_by().values('user').annotate(total=Sum('score')).values('total')

	return queryset.select_related('user', 'user__profile', 'assistant', 'semester').annotate(
		num_psets=SubqueryCount('pset', filter=Q(approved=True, eligible=True)),
		clubs_any=SubquerySum('user__student__pset__clubs', filter=Q(approved=True, eligible=True)),
		clubs_D=SubquerySum(
			'user__student__pset__clubs',
			filter=Q(approved=True, eligible=True, unit__code__startswith='D')
		),
		clubs_Z=SubquerySum(
			'user__student__pset__clubs',
			filter=Q(approved=True, eligible=True, unit__code__startswith='Z')
		),
		hearts=SubquerySum('user__student__pset__hours', filter=Q(approved=True, eligible=True)),
		diamonds=SubquerySum('user__achievementunlock__achievement__diamonds'),
		pset_B_count=SubqueryCount('pset__pk', filter=Q(eligible=True, unit__code__startswith='B')),
		pset_D_count=SubqueryCount('pset__pk', filter=Q(eligible=True, unit__code__startswith='D')),
		pset_Z_count=SubqueryCount('pset__pk', filter=Q(eligible=True, unit__code__startswith='Z')),
		spades_quizzes=SubquerySum('user__student__examattempt__score'),
		spades_quests=SubquerySum('user__student__questcomplete__spades'),
		spades_markets=Subquery(guess_subquery),  # type: ignore
		spades_count_mocks=SubqueryCount('user__student__mockcompleted'),
		spades_suggestions=SubqueryCount(
			'user__problemsuggestion__unit__pk',
			filter=Q(resolved=True, eligible=True),
		),
		# hints definitely not handled here
	)


def compute_insanity_rating(b: int, d: int, z: int) -> float:
	assert min(b, d, z) >= 0
	if b == 0 and d == 0 and z == 0:
		return 0
	return (z - b) / (b + d + z)


def get_student_rows(queryset: QuerySet[Student]) -> List[Dict[str, Any]]:
	rows: List[Dict[str, Any]] = []
	levels: Dict[int, str] = {level.threshold: level.name for level in Level.objects.all()}
	if len(levels) == 0:
		levels[0] = 'No level'
	max_level = max(levels.keys())

	for student in annotate_student_queryset_with_scores(queryset):
		row: Dict[str, Any] = {}
		row['student'] = student
		row['spades'] = (getattr(student, 'spades_quizzes', 0) or 0) * 2
		row['spades'] += (getattr(student, 'spades_quests', 0) or 0)
		# TODO markets
		row['spades'] += (getattr(student, 'spades_count_mocks', 0) or 0) * 3
		row['spades'] += (getattr(student, 'spades_suggestions', 0) or 0)
		row['spades'] += (getattr(student, 'spades_markets', 0) or 0)
		# TODO hints
		row['hearts'] = getattr(student, 'hearts', 0) or 0
		row['clubs'] = getattr(student, 'clubs_any', 0) or 0
		row['clubs'] += BONUS_D_UNIT * (getattr(student, 'clubs_D', 0) or 0)
		row['clubs'] += BONUS_Z_UNIT * (getattr(student, 'clubs_Z', 0) or 0)
		row['diamonds'] = getattr(student, 'diamonds', 0) or 0
		row['level'] = sum(
			int(max(row[k], 0)**0.5) for k in ('spades', 'hearts', 'clubs', 'diamonds')
		)
		try:
			row['last_seen'] = student.user.profile.last_seen
		except UserProfile.DoesNotExist:
			row['last_seen'] = datetime.fromtimestamp(0, tz=timezone.utc)
		row['insanity'] = compute_insanity_rating(
			getattr(student, 'pset_B_count'),
			getattr(student, 'pset_D_count'),
			getattr(student, 'pset_Z_count'),
		)
		if row['level'] > max_level:
			row['level_name'] = levels[max_level]
		else:
			row['level_name'] = levels.get(row['level'], "No level")
		rows.append(row)
	rows.sort(
		key=lambda row: (
			row['student'].semester.pk,
			not row['student'].legit,
			row['student'].track,
			row['student'].user.first_name,
			row['student'].user.last_name,
		)
	)
	return rows


def check_level_up(student: Student) -> bool:
	if not student.semester.active:
		return False
	level_info = get_level_info(student)
	level_number = level_info['level_number']
	if level_number <= student.last_level_seen:
		return False

	bonuses = BonusLevel.objects.filter(active=True, level__lte=level_number)
	bonuses = bonuses.annotate(
		gotten=Exists('bonuslevelunlock', filter=Q(student__user=student.user))
	)
	bonuses = bonuses.exclude(gotten=True)

	if bonuses.exists():
		psets = PSet.objects.filter(student=student)
		counts = psets.aggregate(
			b=Count('pk', unique=True, filter=Q(unit__code__startswith='B')),
			d=Count('pk', unique=True, filter=Q(unit__code__startswith='D')),
			z=Count('pk', unique=True, filter=Q(unit__code__startswith='Z')),
		)
		r = compute_insanity_rating(b=counts['b'], d=counts['d'], z=counts['z'])

		for bonus in bonuses:
			units = bonus.group.unit_set
			if r >= 0.5:
				unit = units.filter(code__startswith='Z').first()
			elif r <= -0.5:
				unit = units.filter(code__startswith='B').first()
			else:
				unit = units.filter(code__startswith='D').first()
			if unit is not None:
				student.curriculum.add(unit)
				BonusLevelUnlock.objects.create(bonus=bonus, student=student)
				logger.log(SUCCESS_LOG_LEVEL, f"{student} obtained special unit {unit}")

	student.last_level_seen = level_number
	student.save()
	return True
