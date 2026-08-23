"""Fills a local database with dummy data that's fun to click around in.

Expects a freshly migrated database with the unit and level fixtures already
loaded; `fixtures/gen-dummy-data.sh` does both of those steps first.
The random seed is fixed, so the shape of the output (how many units each
student has, who submitted which quiz, ...) is the same on every run.
"""

# Django models can't be imported before the app registry is ready,
# hence the imports sitting below the django.setup() call.

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
from tubes.factories import (
    JoinRecordFactory,
    OIMECommentFactory,
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
    TubeFactory,
)
from tubes.models import OIMEContributor, OIMEFight, OIMEProposal

# How many objects to create; each one is also a command-line flag.
# (flag, name, default, help text)
ARGUMENTS: tuple[tuple[str, str, int, str], ...] = (
    ("-s", "stu_num", 25, "number of students"),
    ("-d", "achievement_num", 5, "number of diamonds or achievements"),
    ("-p", "arch_num", 3, "number of arch problems"),
    ("-e", "exam_num", 5, "number of tests and quizzes, respectively"),
    ("-a", "assistant_num", 2, "number of assistants"),
    ("-m", "market_num", 3, "number of markets"),
    ("-o", "oime_num", 20, "number of OIME proposals"),
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

# Dice rolls for the OIME testsolving tube.
P_OIME = 0.5  # chance a user signs up for OIME as a contributor
P_OIME_CASUAL = 0.15  # chance a contributor is currently in casual mode
P_OIME_RETURNED = 0.2  # chance a ranked contributor once dipped into casual mode
P_OIME_ANON = 0.1  # chance a contributor hides their name on leaderboards
P_OIME_DRAFT = 0.15  # chance a proposal is still its author's private draft
P_OIME_ARCHIVED = 0.05  # chance a proposal has been archived by staff
P_OIME_FIGHT = 0.25  # chance a contributor testsolves a given proposal
P_OIME_ACTIVE = 0.05  # chance a testsolve is still in progress right now
P_OIME_UPVOTE = 0.5  # chance a solved proposal gets an upvote from its solver
P_OIME_COMMENT = 0.25  # chance a finished testsolve leaves a comment
P_OIME_REVEAL = 0.1  # chance a contributor spoils a proposal they never fought
OIME_DAYS = 90  # how far back OIME proposals and testsolves are spread
# Weights for how a finished testsolve turned out.
OIME_OUTCOMES = (
    ("OIME_OK", 55),  # solved
    ("OIME_ALE", 15),  # ran out of answer attempts
    ("OIME_TLE", 15),  # ran out of time
    ("OIME_FAIL", 15),  # gave up
)

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


def create_oime_contributors(users: list[User]) -> list[OIMEContributor]:
    """Signs a subset of users up for OIME, and records them joining the tube."""
    print("Creating the OIME tube")
    tube = TubeFactory.create(
        display_name="OIME testsolving",
        description="Testsolving for the OTIS Invitational Mathematics Examination.",
        main_url="https://otis.evanchen.cc/tubes/proposals/",
    )

    joiners = [user for user in users if random.random() < P_OIME]
    now = timezone.now()
    contributor_rows: list[Any] = []
    for user in joiners:
        casual = random.random() < P_OIME_CASUAL
        # A ranked contributor who once browsed casually keeps a cutoff, which
        # leaves every older problem browse-only for them.
        returned = not casual and random.random() < P_OIME_RETURNED
        contributor_rows.append(
            (
                user,
                user.get_full_name() or user.username,
                casual,
                random.random() < P_OIME_ANON,
                now - timedelta(days=random.randint(1, OIME_DAYS))
                if returned
                else None,
            )
        )

    print(f"Creating {len(joiners)} OIME contributors")
    contributors: list[OIMEContributor] = bulk_create_rows(
        OIMEContributorFactory,
        contributor_rows,
        "user",
        "display_name",
        "casual_mode",
        "hide_from_leaderboards",
        "ranked_cutoff",
    )
    print(f"Creating {len(joiners)} join records")
    bulk_create_rows(
        JoinRecordFactory,
        [
            (user, now - timedelta(days=random.randint(1, OIME_DAYS)))
            for user in joiners
        ],
        "user",
        "activation_time",
        tube=tube,
    )
    return contributors


def create_oime_proposals(
    oime_num: int, contributors: list[OIMEContributor]
) -> list[OIMEProposal]:
    """Writes proposals, spread over the last few months, some drafted or archived."""
    subjects = [subject for subject, _ in OIMEProposal.SUBJECT_CHOICES]
    print(f"Creating {oime_num} OIME proposals")
    proposals: list[OIMEProposal] = bulk_create_rows(
        OIMEProposalFactory,
        [
            (
                random.choice(contributors),
                random.choice(subjects),
                randint_low(1, 5),
                random.random() < P_OIME_DRAFT,
                random.random() < P_OIME_ARCHIVED,
            )
            for _ in range(oime_num)
        ],
        "author",
        "subject",
        "difficulty",
        "is_draft",
        "archived",
    )

    # created_at is auto_now_add, so spreading the proposals out over the term
    # has to happen after the insert. Doing it matters: a contributor's
    # ranked_cutoff is compared against it to decide what they may still fight.
    # The stamps are sorted so that creation order matches pk order, the way it
    # does in real life; otherwise the default newest-first list looks shuffled.
    now = timezone.now()
    stamps = sorted(
        now - timedelta(minutes=random.randint(60, OIME_DAYS * 24 * 60))
        for _ in proposals
    )
    for proposal, created_at in zip(proposals, stamps):
        proposal.created_at = created_at
    OIMEProposal.objects.bulk_update(proposals, fields=("created_at",), batch_size=50)
    return proposals


def create_oime_fights(
    contributors: list[OIMEContributor], proposals: list[OIMEProposal]
) -> list[OIMEFight]:
    """Testsolves the published proposals, with a mix of outcomes."""
    now = timezone.now()
    statuses = [status for status, _ in OIME_OUTCOMES]
    weights = [weight for _, weight in OIME_OUTCOMES]

    rows: list[Any] = []
    started: list[datetime] = []
    # At most one active session per contributor, the invariant start_fight enforces.
    busy: set[int] = set()

    for proposal in proposals:
        if proposal.is_draft or proposal.archived:
            continue
        limit = proposal.time_limit_minutes * 60
        for contributor in contributors:
            if contributor.pk == proposal.author_id:  # type: ignore[attr-defined]
                continue
            if random.random() > P_OIME_FIGHT:
                continue

            active = (
                not contributor.casual_mode
                and contributor.pk not in busy
                and random.random() < P_OIME_ACTIVE
            )
            if active:
                busy.add(contributor.pk)
                # Still inside the clock, so the fight page shows a live timer.
                started.append(now - timedelta(seconds=random.randint(0, limit // 2)))
                rows.append((contributor, proposal, "OIME_TBD", 0, None))
                continue

            status = random.choices(statuses, weights)[0]
            start = proposal.created_at + timedelta(
                seconds=random.randint(
                    0, int((now - proposal.created_at).total_seconds())
                )
            )
            started.append(start)
            if status == "OIME_ALE":
                wrong_answers = OIMEFight.ANSWER_LIMIT
            elif status == "OIME_OK":
                wrong_answers = randint_low(0, OIMEFight.ANSWER_LIMIT - 1)
            else:
                wrong_answers = randint_low(0, OIMEFight.ANSWER_LIMIT)
            # A timed-out fight is closed at the buzzer; the rest end whenever.
            spent = limit if status == "OIME_TLE" else random.randint(30, limit)
            rows.append(
                (
                    contributor,
                    proposal,
                    status,
                    wrong_answers,
                    start + timedelta(seconds=spent),
                )
            )

    print(f"Creating {len(rows)} OIME testsolve attempts")
    fights: list[OIMEFight] = bulk_create_rows(
        OIMEFightFactory,
        rows,
        "contributor",
        "proposal",
        "status",
        "wrong_answers",
        "submitted_at",
    )
    # started_at is auto_now_add, so it too can only be backdated after the insert.
    for fight, start in zip(fights, started):
        fight.started_at = start
    OIMEFight.objects.bulk_update(fights, fields=("started_at",), batch_size=50)
    return fights


def create_oime_reactions(
    contributors: list[OIMEContributor],
    proposals: list[OIMEProposal],
    fights: list[OIMEFight],
):
    """Upvotes, revealed solutions and comments left in the wake of the testsolves."""
    UpvoteThroughModel = OIMEProposal.upvotes.through
    RevealedThroughModel = OIMEContributor.revealed_proposals.through

    fought = {(f.contributor_id, f.proposal_id) for f in fights}  # type: ignore[attr-defined]
    upvotes = [
        UpvoteThroughModel(
            oimeproposal_id=fight.proposal_id,  # type: ignore[attr-defined]
            oimecontributor_id=fight.contributor_id,  # type: ignore[attr-defined]
        )
        for fight in fights
        if fight.is_success and random.random() < P_OIME_UPVOTE
    ]
    print(f"Creating {len(upvotes)} OIME upvotes")
    UpvoteThroughModel.objects.bulk_create(upvotes)

    # Reading a solution without solving is the escape hatch out of a problem;
    # it only happens to problems the contributor never fought.
    reveals = [
        RevealedThroughModel(
            oimecontributor_id=contributor.pk, oimeproposal_id=proposal.pk
        )
        for contributor in contributors
        for proposal in proposals
        if not proposal.is_draft
        and contributor.pk != proposal.author_id  # type: ignore[attr-defined]
        and (contributor.pk, proposal.pk) not in fought
        and random.random() < P_OIME_REVEAL
    ]
    print(f"Creating {len(reveals)} revealed OIME solutions")
    RevealedThroughModel.objects.bulk_create(reveals)

    comments = [
        (fight.contributor, fight.proposal)
        for fight in fights
        if fight.is_complete and random.random() < P_OIME_COMMENT
    ]
    print(f"Creating {len(comments)} OIME comments")
    bulk_create_rows(OIMECommentFactory, comments, "author", "proposal")


def create_oime(args: argparse.Namespace, users: list[User]):
    """Creates the OIME tube: contributors, proposals, testsolves and discussion."""
    contributors = create_oime_contributors(users)
    if not contributors:
        return
    proposals = create_oime_proposals(args.oime_num, contributors)
    fights = create_oime_fights(contributors, proposals)
    create_oime_reactions(contributors, proposals, fights)


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
    create_oime(args, users + assistant_users)

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
