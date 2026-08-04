"""Fills a local database with dummy data that's fun to click around in.

Expects a freshly migrated database with the unit and level fixtures already
loaded; `fixtures/gen-dummy-data.sh` does both of those steps first.
The random seed is fixed, so the shape of the output (how many units each
student has, who submitted which quiz, ...) is the same on every run.
"""

# Django models can't be imported before the app registry is ready,
# hence the imports sitting below the django.setup() call.
# ruff: noqa: E402

import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import django

# https://stackoverflow.com/questions/58780717/how-to-use-django-model-in-an-external-python-script-within-the-project
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "otisweb.settings")
django.setup()

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.utils import timezone
from factory.base import Factory
from factory.declarations import Iterator
from factory.fuzzy import FuzzyInteger

from arch.factories import HintFactory, ProblemFactory
from arch.models import Problem
from core.factories import SemesterFactory, UserFactory, UserProfileFactory
from core.models import Semester, Unit
from dashboard.factories import PSetFactory, SemesterDownloadFileFactory
from dashboard.models import PSet
from exams.factories import ExamAttemptFactory, PracticeExamFactory, QuizFactory
from exams.models import PracticeExam
from hanabi.factories import HanabiContestFactory
from markets.factories import GuessFactory, MarketFactory
from markets.models import Market
from opal.factories import OpalHuntFactory
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from roster.models import Assistant, RegistrationContainer, Student, StudentRegistration
from rpg.factories import (
    AchievementFactory,
    AchievementUnlockFactory,
    QuestCompleteFactory,
)
from rpg.models import Achievement
from suggestions.factories import ProblemSuggestionFactory

# How many objects to create; each one is also a command-line flag.
# (flag, name, default, help text)
ARGUMENTS: tuple[tuple[str, str, int, str], ...] = (
    ("-s", "stu_num", 25, "number of students"),
    ("-d", "achievement_num", 5, "number of diamonds or achievements"),
    ("-p", "arch_num", 3, "number of arch problems"),
    ("-e", "exam_num", 5, "number of tests and quizzes, respectively"),
    ("-a", "assistant_num", 2, "number of assistants"),
    ("-m", "market_num", 3, "number of markets"),
)

# Dice rolls deciding who gets what; tweak to taste.
P_SUGGESTION = 0.24  # chance a user writes a problem suggestion
P_PSET = 0.2  # chance a student psets a given unit of their curriculum
P_PSET_APPROVED = 0.9  # chance such a pset is approved rather than pending
P_QUIZ_SKIP = 0.3  # chance a student submits no quizzes at all
P_QUIZ = 0.4  # chance a quiz-taking student submits a given quiz
P_QUEST_SKIP = 0.65  # chance a student completes no quests
P_MARKET_SKIP = 0.2  # chance a student guesses on no markets
P_MARKET_GUESS = 0.8  # chance a guessing student guesses on a given market
P_ASSISTANT = 0.1  # chance a student is assigned an instructor
MAX_STU_UNITS = 27  # largest curriculum a student can be given
MIN_PSET_UNITS = 3  # units at the start of a curriculum that are never pset

## Utils


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populates the local django with some test data."
    )
    for flag, name, default, help_text in ARGUMENTS:
        parser.add_argument(
            flag, dest=name, default=default, metavar="INT", type=int, help=help_text
        )
    return parser.parse_args()


# create_batch doesn't optimize, so here's
# some hacky code to use bulk_create
def fast_bulk_create(cls: type[Factory], size: int, **kwargs: Any) -> Any:  # type: ignore
    return cls._meta.model.objects.bulk_create(cls.build_batch(size, **kwargs))  # type: ignore


def bulk_create_rows(
    cls: type[Factory],  # type: ignore
    rows: list[Any],
    *fields: str,
    **kwargs: Any,
) -> Any:
    """Creates one object per row, unpacking each row tuple into `fields`."""
    columns = list(zip(*rows)) or [()] * len(fields)
    return fast_bulk_create(
        cls,
        len(rows),
        **kwargs,
        **{field: Iterator(column) for field, column in zip(fields, columns)},
    )


# silly thing with slight bias for small numbers
def randint_low(a: int, b: int) -> int:
    return a + b - round(math.sqrt(random.randint(a**2, b**2)))


def random_pairs[T, S](
    rows: list[T], cols: list[S], p_skip: float, p_pair: float
) -> list[tuple[T, S]]:
    """Matches rows against cols, e.g. students against the quizzes they took.

    Each row is left out entirely with probability `p_skip`;
    the rest are paired with each col with probability `p_pair`.
    """
    pairs: list[tuple[T, S]] = []
    for row in rows:
        if random.random() < p_skip:
            continue
        pairs += [(row, col) for col in cols if random.random() < p_pair]
    return pairs


## Creation


def create_exams(exam_num: int, family: str, start_date: datetime):
    """Creates a family's worth of practice tests and quizzes."""
    for factory in (PracticeExamFactory, QuizFactory):
        fast_bulk_create(
            factory,
            exam_num,
            family=family,
            start_date=start_date,
            due_date=Iterator(
                start_date + timedelta(days=50 * i + 50) for i in range(exam_num)
            ),
            number=Iterator(range(1, exam_num + 1)),
        )


# Creates models independent of a semester
def create_sem_independent(args: argparse.Namespace, users: list[User]):
    # achievements - 24 digit collision is basically impossible
    print(f"Creating {args.achievement_num} achievements")
    fast_bulk_create(
        AchievementFactory, args.achievement_num, diamonds=FuzzyInteger(3, 7)
    )

    # arch problems and hints
    print(f"Creating {args.arch_num} ARCH problems")
    problems: list[Problem] = fast_bulk_create(ProblemFactory, args.arch_num)
    hints: list[tuple[Problem, int]] = []
    for problem in problems:
        hint_num = randint_low(0, 10)
        hints += [(problem, percent) for percent in random.sample(range(101), hint_num)]
    print(f"Creating {len(hints)} hints")
    bulk_create_rows(HintFactory, hints, "problem", "number")

    # exams
    print(f"Creating {args.exam_num * 4} exam objects")
    now = timezone.now()
    create_exams(args.exam_num, "Waltz", now)
    create_exams(args.exam_num, "Foxtrot", now - timedelta(days=365))

    # users
    print(f"Creating {len(users)} user profiles")
    fast_bulk_create(UserProfileFactory, len(users), user=Iterator(users))

    units: list[Unit] = list(Unit.objects.all())
    achievements: list[Achievement] = list(Achievement.objects.all())
    max_stu_achievements = round(math.sqrt(len(achievements)))

    unlocks: list[tuple[User, Achievement]] = []
    suggestions: list[tuple[User, Unit]] = []
    for user in users:
        if args.achievement_num > 0:
            stu_achievements = random.sample(
                achievements, randint_low(0, max_stu_achievements)
            )
            unlocks += [(user, achievement) for achievement in stu_achievements]

        if random.random() < P_SUGGESTION:
            suggestions.append((user, random.choice(units)))

    print(f"Creating {len(unlocks)} achievement unlocks")
    bulk_create_rows(AchievementUnlockFactory, unlocks, "user", "achievement")
    print(f"Creating {len(suggestions)} problem suggestions")
    bulk_create_rows(ProblemSuggestionFactory, suggestions, "user", "unit")

    print("Creating an Opal hunt")
    OpalHuntFactory.create(name="Your Otis in April", slug="your-otis-in-april")

    print("Creating a Hanabi contest")
    HanabiContestFactory.create()


def assign_curriculums(students: list[Student]):
    """Gives each student some units, unlocking and psetting a few of them."""
    units = list(Unit.objects.all())
    max_stu_units = min(len(units), MAX_STU_UNITS)
    min_pset_units = min(max_stu_units, MIN_PSET_UNITS)

    # https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452
    CurriculumThroughModel = Student.curriculum.through
    UnlockedThroughModel = Student.unlocked_units.through

    curriculum_bulk = []
    unlocked_units_bulk = []
    psets: list[PSet] = []

    print("Populating curriculums and creating psets (this could take a while...)")
    for student in students:
        stu_curriculum_num = random.randint(1, max_stu_units)
        stu_unlocked_num = random.randint(1, stu_curriculum_num)
        stu_units = random.sample(units, stu_curriculum_num)

        curriculum_bulk += [
            CurriculumThroughModel(student_id=student.pk, unit_id=unit.pk)
            for unit in stu_units
        ]
        unlocked_units_bulk += [
            UnlockedThroughModel(student_id=student.pk, unit_id=unit.pk)
            for unit in stu_units[:stu_unlocked_num]
        ]

        # the last unit is left alone, so that every pset has a unit to unlock
        for i in range(min_pset_units, stu_curriculum_num - 1):
            if random.random() > P_PSET:
                continue
            status = "P" if random.random() > P_PSET_APPROVED else "A"
            psets.append(
                PSetFactory.build(
                    student=student,
                    unit=stu_units[i],
                    next_unit_to_unlock=stu_units[i + 1],
                    hours=random.randint(1, 54),
                    clubs=random.randint(30, 200),
                    status=status,
                )
            )

    CurriculumThroughModel.objects.bulk_create(curriculum_bulk)
    UnlockedThroughModel.objects.bulk_create(unlocked_units_bulk)

    print(f"Creating {len(psets)} problem sets")
    PSet.objects.bulk_create(psets, batch_size=50)


def create_quiz_attempts(students: list[Student], quizzes: list[PracticeExam]):
    attempts = random_pairs(students, quizzes, P_QUIZ_SKIP, P_QUIZ)
    print(f"Creating {len(attempts)} quiz submissions")
    bulk_create_rows(
        ExamAttemptFactory, attempts, "student", "quiz", score=FuzzyInteger(0, 5)
    )


def create_quest_completes(students: list[Student]):
    completers: list[Student] = []
    for student in students:
        if random.random() < P_QUEST_SKIP:
            continue
        completers += [student] * random.randrange(1, 3)
    print(f"Creating {len(completers)} quest completes")
    fast_bulk_create(
        QuestCompleteFactory, len(completers), student=Iterator(completers)
    )


def create_market_guesses(students: list[Student], markets: list[Market]):
    guesses = random_pairs(
        [student.user for student in students], markets, P_MARKET_SKIP, P_MARKET_GUESS
    )
    print(f"Creating {len(guesses)} guesses for markets")
    bulk_create_rows(GuessFactory, guesses, "user", "market")


def assign_assistants(students: list[Student]):
    assistants = list(Assistant.objects.all())
    if not assistants:
        return
    lucky_students: list[Student] = []
    for student in students:
        if random.random() < P_ASSISTANT:
            student.assistant = random.choice(assistants)
            lucky_students.append(student)
    print(f"Assigning instructors to {len(lucky_students)} students")
    Student.objects.bulk_update(lucky_students, fields=("assistant",), batch_size=50)


# Creates models dependent on a semester
def create_sem_dependent(
    args: argparse.Namespace, semester: Semester, users: list[User]
):
    container: RegistrationContainer = RegistrationContainerFactory.create(
        semester=semester
    )
    SemesterDownloadFileFactory.create(semester=semester)
    markets: list[Market] = fast_bulk_create(
        MarketFactory, args.market_num, semester=semester
    )
    quizzes = list(
        PracticeExam.objects.filter(
            is_test=False,
            family="Waltz" if semester.active else "Foxtrot",
        )
    )

    print(f"Creating {len(users)} students, with invoices and registrations")
    students: list[Student] = fast_bulk_create(
        StudentFactory,
        len(users),
        semester=semester,
        user=Iterator(users),
    )
    fast_bulk_create(InvoiceFactory, len(users), student=Iterator(students))
    regs: list[StudentRegistration] = fast_bulk_create(
        StudentRegistrationFactory,
        len(users),
        container=container,
        user=Iterator(users),
    )
    for student, reg in zip(students, regs):
        student.reg = reg
    Student.objects.bulk_update(students, fields=("reg",), batch_size=50)

    assign_curriculums(students)
    create_quiz_attempts(students, quizzes)
    create_quest_completes(students)
    create_market_guesses(students, markets)
    assign_assistants(students)


def main():
    args = parse_args()
    settings.TESTING = True
    random.seed("OTIS-WEB")

    verified_group, _ = Group.objects.get_or_create(name="Verified")
    staff_group, _ = Group.objects.get_or_create(name="Active Staff")

    print(f"Creating {args.stu_num} user accounts")
    users: list[User] = fast_bulk_create(UserFactory, args.stu_num)
    # bulk_create can't set many-to-many fields, so do the group by hand
    verified_group.user_set.set([user.pk for user in users])  # type: ignore

    # assistants - technically O(n) but only a couple by default
    print(f"Creating {args.assistant_num} assistants")
    assistant_users: list[User] = UserFactory.create_batch(
        args.assistant_num,
        groups=(verified_group, staff_group),
        is_staff=True,
    )
    fast_bulk_create(
        AssistantFactory, args.assistant_num, user=Iterator(assistant_users)
    )

    create_sem_independent(args, users)

    current_year = timezone.now().year
    old_semester: Semester = SemesterFactory.create(
        show_invoices=False,
        active=False,
        end_year=current_year - 1,
        exam_family="Foxtrot",
    )
    current_semester: Semester = SemesterFactory.create(
        show_invoices=True,
        end_year=current_year,
        exam_family="Waltz",
    )

    create_sem_dependent(
        args, old_semester, random.sample(users, int(0.6 * len(users)))
    )
    create_sem_dependent(
        args, current_semester, random.sample(users, int(0.7 * len(users)))
    )


if __name__ == "__main__":
    main()
