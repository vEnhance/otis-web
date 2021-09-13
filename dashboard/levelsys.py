# Functions to compute student levels and whatnot
from typing import Any, Dict, List, TypedDict, Union

from django.db.models.aggregates import Sum
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from exams.models import ExamAttempt
from roster.models import Student
from sql_util.aggregates import SubqueryCount, SubquerySum

from dashboard.models import AchievementUnlock, Level, PSet, QuestComplete

BONUS_D_UNIT = 0.3
BONUS_Z_UNIT = 0.5


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
		return int(self.value**0.5)

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


class LevelInfoDict(TypedDict):
	psets: QuerySet[PSet]
	pset_data: AggregateDict
	quiz_attempts: QuerySet[ExamAttempt]
	quest_completes: QuerySet[QuestComplete]
	meters: Any  # TODO
	level_number: int
	level_name: str


def get_level_info(student: Student) -> LevelInfoDict:
	"""Uses a bunch of expensive database queries to compute a student's levels and data,
	returning the findings as a (TODO typed) dictionary."""

	psets = PSet.objects.filter(student=student, approved=True, eligible=True)
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

	quiz_attempts = ExamAttempt.objects.filter(student=student)
	quest_completes = QuestComplete.objects.filter(student=student)
	total_spades = quiz_attempts.aggregate(Sum('score'))['score__sum'] or 0
	total_spades += quest_completes.aggregate(Sum('spades'))['spades__sum'] or 0

	meters = {
		'clubs': Meter.ClubMeter(int(total_clubs)),
		'hearts': Meter.HeartMeter(int(total_hearts)),
		'diamonds': Meter.DiamondMeter(total_diamonds),
		'spades': Meter.SpadeMeter(total_spades),  # TODO input value
	}
	level_number = sum(meter.level for meter in meters.values())
	level = Level.objects.filter(threshold__lte=level_number).order_by('-threshold').first()
	level_name = level.name if level is not None else 'No Level'
	level_data: LevelInfoDict = {
		'psets': psets,
		'pset_data': pset_data,
		'quiz_attempts': quiz_attempts,
		'quest_completes': quest_completes,
		'meters': meters,
		'level_number': level_number,
		'level_name': level_name
	}
	return level_data


def annotate_student_queryset_with_scores(queryset: QuerySet[Student]) -> QuerySet[Student]:
	"""Helper function for constructing large lists of students
	Selects all important information to prevent a bunch of SQL queries"""
	return queryset.select_related('user', 'assistant', 'semester').annotate(
		num_psets=SubqueryCount('pset', filter=Q(approved=True, eligible=True)),
		clubs_any=SubquerySum('pset__clubs', filter=Q(approved=True, eligible=True)),
		clubs_D=SubquerySum(
			'pset__clubs', filter=Q(approved=True, eligible=True, unit__code__startswith='D')
		),
		clubs_Z=SubquerySum(
			'pset__clubs', filter=Q(approved=True, eligible=True, unit__code__startswith='Z')
		),
		hearts=SubquerySum('pset__hours', filter=Q(approved=True, eligible=True)),
		spades_quizzes=SubquerySum('examattempt__score'),
		spades_quests=SubquerySum('questcomplete__spades'),
		diamonds=SubquerySum('user__achievementunlock__achievement__diamonds'),
	)


def get_student_rows(queryset: QuerySet[Student]) -> List[Dict[str, Any]]:
	rows: List[Dict[str, Any]] = []
	levels: Dict[int, str] = {level.threshold: level.name for level in Level.objects.all()}
	if len(levels) == 0:
		levels[0] = 'No level'
	max_level = max(levels.keys())

	for student in annotate_student_queryset_with_scores(queryset):
		row: Dict[str, Any] = {}
		row['student'] = student
		row['spades'] = (getattr(student, 'spades_quizzes', 0) or 0)
		row['spades'] += (getattr(student, 'spades_quests', 0) or 0)
		row['hearts'] = getattr(student, 'hearts', 0) or 0
		row['clubs'] = getattr(student, 'clubs_any', 0) or 0
		row['clubs'] += BONUS_D_UNIT * (getattr(student, 'clubs_D', 0) or 0)
		row['clubs'] += BONUS_Z_UNIT * (getattr(student, 'clubs_Z', 0) or 0)
		row['diamonds'] = getattr(student, 'diamonds', 0) or 0
		row['level'] = sum(int(row[k]**0.5) for k in ('spades', 'hearts', 'clubs', 'diamonds'))
		if row['level'] > max_level:
			row['level_name'] = levels[max_level]
		else:
			row['level_name'] = levels.get(row['level'], "No level")
		rows.append(row)
	return rows
