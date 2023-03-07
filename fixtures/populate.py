# TODO: this entire thing is a giant hack that could be really cleaned up

import argparse
import math
import os
import random
from datetime import datetime, timedelta

import django
from django.conf import settings

random.seed("OTIS-WEB")

# hack to unindent following code
if __name__ != "__main__":
    raise TypeError("Attempted to import command-line only script")

# https://stackoverflow.com/questions/58780717/how-to-use-django-model-in-an-external-python-script-within-the-project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "otisweb.settings")
django.setup()
settings.TESTING = True

import factory
from django.contrib.auth.models import Group, User
from factory.fuzzy import FuzzyInteger

from arch.factories import HintFactory, ProblemFactory, VoteFactory
from arch.models import Problem
from core.factories import SemesterFactory, UserFactory, UserProfileFactory
from core.models import Semester, Unit
from dashboard.factories import SemesterDownloadFileFactory
from dashboard.models import PSet
from exams.factories import ExamAttemptFactory, QuizFactory, TestFactory
from exams.models import PracticeExam
from markets.factories import GuessFactory, MarketFactory
from markets.models import Market
from roster.factories import (
    AssistantFactory,
    InvoiceFactory,
    RegistrationContainerFactory,
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
        default=100,
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
    print(f"Creating {args.achievement_num} achievements")
    AchievementFactory.create_batch(args.achievement_num, diamonds=FuzzyInteger(3, 7))

    # arch problems and hints
    print(f"Creating {args.arch_num} ARCH problems")
    problems = ProblemFactory.create_batch(args.arch_num)
    hint_seq_data: list[tuple[Problem, int]] = []
    for problem in problems:
        hint_num = randint_low(0, 10)
        for percent in random.sample(range(0, 101), hint_num):
            hint_seq_data.append((problem, percent))

    HintFactory.create_batch(
        len(hint_seq_data),
        problem=factory.Sequence(lambda i: hint_seq_data[i][0]),
        number=factory.Sequence(lambda i: hint_seq_data[i][1]),
    )

    # exams
    print(f"Creating {args.exam_num*4} exam objects")
    TestFactory.create_batch(
        args.exam_num,
        family="Waltz",
        start_date=datetime.now(),
        due_date=factory.Iterator(
            [datetime.now() + timedelta(days=50 * i + 50) for i in range(args.exam_num)]
        ),
        number=factory.Iterator(range(1, args.exam_num + 1)),
    )
    QuizFactory.create_batch(
        args.exam_num,
        family="Waltz",
        start_date=datetime.now(),
        due_date=factory.Iterator(
            [datetime.now() + timedelta(days=50 * i + 50) for i in range(args.exam_num)]
        ),
        number=factory.Iterator(range(1, args.exam_num + 1)),
    )
    last_year = datetime.now() + timedelta(days=-365)
    TestFactory.create_batch(
        args.exam_num,
        family="Foxtrot",
        start_date=last_year,
        due_date=factory.Iterator(
            [last_year + timedelta(days=50 * i + 50) for i in range(args.exam_num)]
        ),
        number=factory.Iterator(range(1, args.exam_num + 1)),
    )
    QuizFactory.create_batch(
        args.exam_num,
        family="Foxtrot",
        start_date=last_year,
        due_date=factory.Iterator(
            [last_year + timedelta(days=50 * i + 50) for i in range(args.exam_num)]
        ),
        number=factory.Iterator(range(1, args.exam_num + 1)),
    )

    # users
    units: list[Unit] = list(Unit.objects.all())
    achievements: list[Achievement] = list(Achievement.objects.all())
    max_stu_achievements = round(math.sqrt(len(achievements)))
    problems: list[Problem] = list(Problem.objects.all())

    UserProfileFactory.create_batch(
        len(users), user=factory.Sequence(lambda i: users[i])
    )

    achievement_seq_data: list[tuple[User, Achievement]] = []
    vote_seq_data: list[tuple[User, Problem]] = []
    suggest_seq_data: list[tuple[User, Unit]] = []

    for user in users:
        # achievement unlocks
        if args.achievement_num > 0:
            stu_achievements = random.sample(
                achievements, randint_low(0, max_stu_achievements)
            )

            for achievement in stu_achievements:
                achievement_seq_data.append((user, achievement))

        # votes
        if args.arch_num > 0 and random.random() < 0.2:
            stu_vote_num = random.randint(0, 5)
            stu_vote_problems = random.sample(problems, stu_vote_num)

            for problem in stu_vote_problems:
                vote_seq_data.append((user, problem))

        # suggestions
        if random.random() < 0.24:
            suggest_seq_data.append((user, random.choice(units)))

    print(f"Creating {len(achievement_seq_data)} achievement unlocks")
    AchievementUnlockFactory.create_batch(
        len(achievement_seq_data),
        user=factory.Sequence(lambda i: achievement_seq_data[i][0]),
        achievement=factory.Sequence(lambda i: achievement_seq_data[i][1]),
    )
    print(f"Creating {len(vote_seq_data)} ARCH votes")
    VoteFactory.create_batch(
        len(vote_seq_data),
        user=factory.Sequence(lambda i: vote_seq_data[i][0]),
        problem=factory.Sequence(lambda i: vote_seq_data[i][1]),
    )
    print(f"Creating {len(suggest_seq_data)} problem suggestions")
    ProblemSuggestionFactory.create_batch(
        len(suggest_seq_data),
        user=factory.Sequence(lambda i: suggest_seq_data[i][0]),
        unit=factory.Sequence(lambda i: suggest_seq_data[i][1]),
    )


def create_sem_dependent(semester: Semester, users: list[User]):
    container: RegistrationContainer = RegistrationContainerFactory.create(
        semester=semester
    )

    # download file
    SemesterDownloadFileFactory.create(semester=semester)

    # markets
    markets: list[Market] = MarketFactory.create_batch(
        args.market_num, semester=semester
    )

    # randomly select a few units to be populated for students
    units = list(Unit.objects.all())
    quizzes = list(
        PracticeExam.objects.all().filter(
            is_test=False,
            family="Waltz" if semester.active else "Foxtrot",
        )
    )
    assistants = list(Assistant.objects.all())

    max_stu_units = min(len(units), 27)
    min_stu_units = min(max_stu_units, 3)

    print(f"Creating {len(users)} students and their invoices")
    invoices = InvoiceFactory.create_batch(
        len(users),
        student__user=factory.Iterator(users),
        student__reg__container=container,
        student__reg__processed=True,
        student__semester=semester,
    )
    students = [invoice.student for invoice in invoices]

    print("Populating curriculums and creating psets (this could take a while...)")
    psets: list[PSet] = []

    for student in students:
        # add a few units
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
                psets.append(
                    PSet(
                        student=student,
                        unit=stu_units[i],
                        next_unit_to_unlock=stu_units[i + 1],
                        hours=random.randint(1, 54),
                        clubs=random.randint(30, 200),
                        status=status,
                    )
                )
    print(f"Creating {len(psets)} problem sets")
    PSet.objects.bulk_create(psets, batch_size=50)

    # Quiz attempts
    student_iter_data_for_quizzes: list[Student] = []
    quiz_iter_data: list[PracticeExam] = []
    for student in students:
        if random.random() < 0.3:
            continue
        for quiz in quizzes:
            if random.random() < 0.4:
                student_iter_data_for_quizzes.append(student)
                quiz_iter_data.append(quiz)
    print(f"Creating {len(student_iter_data_for_quizzes)} quiz submissions")
    ExamAttemptFactory.create_batch(
        len(student_iter_data_for_quizzes),
        student=factory.Iterator(student_iter_data_for_quizzes),
        quiz=factory.Iterator(quiz_iter_data),
        score=FuzzyInteger(0, 5),
    )

    # Quest completes
    student_iter_data_for_quests: list[Student] = []
    for student in students:
        for _ in range(random.randrange(1, 3)):
            student_iter_data_for_quests.append(student)
    print(f"Creating {len(student_iter_data_for_quests)} quest completes")
    QuestCompleteFactory.create_batch(
        len(student_iter_data_for_quests),
        student=factory.Iterator(student_iter_data_for_quests),
    )

    # Markets
    user_iter_data_for_markets: list[User] = []
    market_iter_data: list[Market] = []
    for student in students:
        if random.random() < 0.2:
            continue
        for market in markets:
            if random.random() < 0.8:
                user_iter_data_for_markets.append(student.user)
                market_iter_data.append(market)
    print(f"Creating {len(user_iter_data_for_markets)} guesses for markets")
    GuessFactory.create_batch(
        len(user_iter_data_for_markets),
        user=factory.Iterator(user_iter_data_for_markets),
        market=factory.Iterator(market_iter_data),
    )

    students_who_got_assistants: list[Student] = []
    for student in students:
        if args.assistant_num > 0 and random.random() < 0.1:
            student.assistant = random.choice(assistants)
            students_who_got_assistants.append(student)
    print(f"Assigning instructors to {len(students_who_got_assistants)} students")
    Student.objects.bulk_update(
        students_who_got_assistants, fields=("assistant",), batch_size=50
    )


def init():
    args = parse_args()
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    staff_group, _ = Group.objects.get_or_create(name="Active Staff")

    print(f"Creating {args.stu_num} user accounts")
    # users
    users = UserFactory.create_batch(args.stu_num, groups=(verified_group,))

    # assistants
    print(f"Creating {args.assistant_num} assistants")
    AssistantFactory.create_batch(
        args.assistant_num, user__groups=(verified_group, staff_group)
    )

    current_year = datetime.now().year
    create_sem_independent(users)

    old_semester: Semester = SemesterFactory.create(
        show_invoices=False, active=False, end_year=current_year - 1
    )
    current_semester: Semester = SemesterFactory.create(
        show_invoices=True, end_year=current_year
    )

    create_sem_dependent(old_semester, random.sample(users, int(0.6 * len(users))))
    create_sem_dependent(current_semester, random.sample(users, int(0.7 * len(users))))


init()
