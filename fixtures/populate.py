import argparse
import math
import os
import random
from datetime import datetime, timedelta

import django
from django.conf import settings

# hack to unindent following code
if __name__ != "__main__":
    raise TypeError("Attempted to import command-line only script")

# https://stackoverflow.com/questions/58780717/how-to-use-django-model-in-an-external-python-script-within-the-project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "otisweb.settings")
django.setup()
settings.TESTING = True

from django.contrib.auth.models import Group, User

from arch.factories import HintFactory, ProblemFactory, VoteFactory
from arch.models import Problem
from core.factories import SemesterFactory, UserFactory, UserProfileFactory
from core.models import Semester, Unit
from dashboard.factories import PSetFactory, SemesterDownloadFileFactory
from exams.factories import ExamAttemptFactory, QuizFactory, TestFactory
from exams.models import PracticeExam
from markets.factories import GuessFactory, MarketFactory
from markets.models import Market
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
)
from roster.models import Assistant, RegistrationContainer, Student
from rpg.factories import (
    AchievementFactory,
    AchievementUnlockFactory,
    QuestCompleteFactory,
)
from rpg.models import Achievement
from suggestions.factories import ProblemSuggestionFactory


def parse_args() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Populates the local django with some test data."
    )
    parser.add_argument(
        "-s",
        dest="stu_num",
        default=1000,
        metavar="INT",
        type=int,
        help="number of students",
    )
    parser.add_argument(
        "-d",
        dest="achievement_num",
        default=10,
        metavar="INT",
        type=int,
        help="number of diamonds or achievements",
    )
    parser.add_argument(
        "-p",
        dest="arch_num",
        default=30,
        metavar="INT",
        type=int,
        help="number of arch problems",
    )
    parser.add_argument(
        "-e",
        dest="exam_num",
        default=5,
        metavar="INT",
        type=int,
        help="number of tests and quizzes, respectively",
    )
    parser.add_argument(
        "-a",
        dest="assistant_num",
        default=5,
        metavar="INT",
        type=int,
        help="number of assistants",
    )
    parser.add_argument(
        "-m",
        dest="market_num",
        default=3,
        metavar="INT",
        type=int,
        help="number of markets",
    )

    return parser.parse_args()


args = parse_args()


# silly thing with slight bias for small numbers
def randint_low(a: int, b: int) -> int:
    return (a + b) - round(math.sqrt(random.randint(a * a, b * b)))


def create_sem_independent(users: list[User]):
    # achievements - 24 digit collision is basically impossible
    for i in range(0, args.achievement_num):
        AchievementFactory.create(diamonds=randint_low(1, 6))

    # arch problems and hints
    problems: list[Problem] = ProblemFactory.create_batch(args.arch_num)

    for problem in problems:
        hint_num = randint_low(0, 10)

        hint_percentages: list[int] = random.sample(range(0, 101), hint_num)

        for percentage in hint_percentages:
            HintFactory.create(number=percentage, problem=problem)

    # exams
    for i in range(0, args.exam_num):
        TestFactory.create(
            start_date=datetime.now(),
            due_date=(datetime.now() + timedelta(days=50 * i + 50)),
        )
        QuizFactory.create(
            start_date=datetime.now(),
            due_date=(datetime.now() + timedelta(days=50 * i + 50)),
        )

    # users
    units: list[Unit] = list(Unit.objects.all())
    achievements: list[Achievement] = list(Achievement.objects.all())
    max_stu_achievements = round(math.sqrt(len(achievements)))
    problems: list[Problem] = list(Problem.objects.all())

    for user in users:
        UserProfileFactory.create(user=user)

        # achievement unlocks
        if args.achievement_num > 0:
            stu_achievements = random.sample(
                achievements, randint_low(0, max_stu_achievements)
            )

            for achievement in stu_achievements:
                AchievementUnlockFactory.create(user=user, achievement=achievement)

        # votes
        if args.arch_num > 0:
            stu_vote_num = random.randint(0, 5)
            stu_vote_problems = random.sample(problems, stu_vote_num)

            for problem in stu_vote_problems:
                VoteFactory.create(user=user, problem=problem)

        # suggestions
        if random.random() < 0.24:
            ProblemSuggestionFactory.create(user=user, unit=random.choice(units))


def create_sem_dependent(semester: Semester, users: list[User]):
    container: RegistrationContainer = RegistrationContainerFactory.create(
        semester=semester
    )

    # students
    # download file
    SemesterDownloadFileFactory.create(semester=semester)

    # markets
    markets: list[Market] = MarketFactory.create_batch(
        args.market_num, semester=semester
    )

    # randomly select a few units to be populated for students
    units = list(Unit.objects.all())
    quizzes = list(PracticeExam.objects.all().filter(is_test=False))
    assistants = list(Assistant.objects.all())

    max_stu_units = min(len(units), 27)
    min_stu_units = min(max_stu_units, 3)

    for user in users:
        student: Student = StudentFactory.create(
            user=user,
            reg=StudentRegistrationFactory.create(container=container, processed=True),
            semester=semester,
        )
        InvoiceFactory.create(student=student)

        # add a few units
        if args.unit_num > 0:
            stu_curriculum_num = random.randint(1, max_stu_units)
            stu_unlocked_num = random.randint(1, stu_curriculum_num)
            stu_units = random.sample(units, stu_curriculum_num)

            student.curriculum.set(stu_units)
            student.unlocked_units.set(stu_units[:stu_unlocked_num])

            if stu_curriculum_num > min_stu_units + 1:
                for i in range(min_stu_units, stu_curriculum_num - 1):
                    if random.random() > 0.2:
                        continue

                    if random.random() > 0.9:
                        status = "P"
                    else:
                        status = "A"

                    PSetFactory.create(
                        student=student,
                        unit=stu_units[i],
                        next_unit_to_unlock=stu_units[i + 1],
                        hours=random.randint(1, 54),
                        clubs=random.randint(30, 200),
                        status=status,
                    )

                    break

        # also quizzes
        if random.random() < 0.16:
            ExamAttemptFactory.create(
                student=student, quiz=random.choice(quizzes), score=5
            )

        # assign instructor
        if args.assistant_num > 0 and random.random() < 0.1:
            student.assistant = random.choice(assistants)
            student.save()

        # other spade activities
        if random.random() < 0.12:
            QuestCompleteFactory.create_batch(random.randint(1, 3), student=student)

        # also markets
        if random.random() < 0.2:
            GuessFactory.create(user=user, market=random.choice(markets))


def init():
    args = parse_args()

    # users
    users = UserFactory.create_batch(args.stu_num)

    # assistants
    assistants = AssistantFactory.create_batch(args.assistant_num)

    group, _ = Group.objects.get_or_create(name="Active Staff")
    for assistant in assistants:
        group.user_set.add(assistant.user)  # type: ignore

    old_users = random.sample(users, randint_low(len(users) // 3, len(users) // 2))

    current_year = datetime.now().year
    create_sem_independent(users)
    if len(old_users) > 0:
        old_semester: Semester = SemesterFactory.create(
            show_invoices=False, active=False, end_year=current_year - 1
        )

        create_sem_dependent(old_semester, old_users)

    semester: Semester = SemesterFactory.create(
        show_invoices=True, end_year=current_year
    )
    create_sem_dependent(semester, users)


init()
