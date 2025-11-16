import datetime

import pytest
from django.test.utils import override_settings
from freezegun import freeze_time

from core.factories import SemesterFactory, UserFactory
from exams.calculator import expr_compute
from exams.factories import QuizFactory, TestFactory
from exams.models import ExamAttempt, PracticeExam
from roster.factories import StudentFactory
from roster.models import Student

UTC = datetime.timezone.utc


def check_calculator(expr: str, out: float):
    v = expr_compute(expr)
    assert v is not None
    assert v == pytest.approx(out)


@pytest.mark.django_db
def test_arithmetic():
    check_calculator("1/3^4", 1 / 81)
    check_calculator("(2*sqrt(2))^2 - 4^(3/2)", 0)
    check_calculator("16900/4*pi", 13273.2289614)


@pytest.mark.django_db
def test_pdf():
    pass


@pytest.fixture
def exam_setup():
    semester = SemesterFactory(active=True, exam_family="Waltz")
    semester_old = SemesterFactory(active=False, exam_family="Waltz")
    alice = StudentFactory.create(
        user__username="alice",
        semester=semester,
        user__first_name="Alice",
        user__last_name="Aardvark",
    )
    bob = StudentFactory.create(
        user__username="bob",
        semester=semester_old,
        user__first_name="Bob",
        user__last_name="Beta",
    )
    dead = StudentFactory.create(
        user__username="dead",
        enabled=False,
        semester=semester,
        user__first_name="Dead",
        user__last_name="Derp",
    )

    with override_settings(TESTING_NEEDS_MOCK_MEDIA=True):
        for factory in (TestFactory, QuizFactory):
            for family in ("Waltz", "Foxtrot"):
                factory.create(
                    start_date=datetime.datetime(2020, 1, 1, tzinfo=UTC),
                    due_date=datetime.datetime(2020, 12, 31, tzinfo=UTC),
                    family=family,
                    number=1,
                )
    PracticeExam.objects.filter(is_test=False).update(
        answer1=1000,
        answer2=2000,
        answer3=3000,
        answer4=4000,
        answer5=5000,
    )

    return {
        "semester": semester,
        "semester_old": semester_old,
        "alice": alice,
        "bob": bob,
        "dead": dead,
    }


@pytest.mark.django_db
def test_exam_pdf(otis, exam_setup):
    exam_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
    exam_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

    with freeze_time("2018-01-01", tz_offset=0):
        otis.login("alice")
        otis.get_denied("exam-pdf", exam_waltz.pk)
        otis.get_denied("exam-pdf", exam_foxtrot.pk)
    with freeze_time("2020-06-05", tz_offset=0):
        otis.login("alice")
        otis.get_20x("exam-pdf", exam_waltz.pk)
        otis.get_denied("exam-pdf", exam_foxtrot.pk)
    with freeze_time("2022-12-31", tz_offset=0):
        otis.login("alice")
        otis.get_20x("exam-pdf", exam_waltz.pk)
        otis.get_denied("exam-pdf", exam_foxtrot.pk)

    with freeze_time("2020-06-05", tz_offset=0):
        otis.login("dead")
        otis.get_denied("exam-pdf", exam_waltz.pk)
        otis.get_denied("exam-pdf", exam_foxtrot.pk)

    staff = UserFactory.create(is_staff=True)
    with freeze_time("2018-01-01", tz_offset=0):
        otis.login(staff)
        otis.get_20x("exam-pdf", exam_waltz.pk)
        otis.get_20x("exam-pdf", exam_foxtrot.pk)
    with freeze_time("2020-06-05", tz_offset=0):
        otis.login(staff)
        otis.get_20x("exam-pdf", exam_waltz.pk)
        otis.get_20x("exam-pdf", exam_foxtrot.pk)
    with freeze_time("2022-12-31", tz_offset=0):
        otis.login(staff)
        otis.get_20x("exam-pdf", exam_waltz.pk)
        otis.get_20x("exam-pdf", exam_foxtrot.pk)


@pytest.mark.django_db
def test_quiz(otis, exam_setup):
    alice = exam_setup["alice"]
    quiz_waltz = PracticeExam.objects.get(family="Waltz", is_test=False)
    quiz_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=False)
    test_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
    test_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

    with freeze_time("2018-01-01", tz_offset=0):
        otis.login("alice")
        otis.get_denied("quiz", alice.pk, quiz_waltz.pk)
        otis.get_denied("quiz", alice.pk, test_waltz.pk)
        otis.get_denied("quiz", alice.pk, test_foxtrot.pk)
        otis.get_denied("quiz", alice.pk, quiz_foxtrot.pk)
    with freeze_time("2020-06-05", tz_offset=0):
        otis.login("dead")
        otis.get_denied(
            "quiz", Student.objects.get(user__username="dead").pk, quiz_waltz.pk
        )
        otis.login("alice")
        otis.get_denied("quiz", alice.pk, test_waltz.pk)
        otis.get_denied("quiz", alice.pk, test_foxtrot.pk)
        otis.get_denied("quiz", alice.pk, quiz_foxtrot.pk)

        # OK, now actually take a quiz, lol
        resp_before_submit = otis.get_20x("quiz", alice.pk, quiz_waltz.pk)
        otis.assert_has(resp_before_submit, "Submit answers")

        # submit quiz improperly
        resp_after_improper = otis.post_20x(
            "quiz",
            alice.pk,
            quiz_waltz.pk,
            data={
                "guess1": r"$@#%$@#\^__meow__^%&*(==",
                "guess2": "2000",
            },
        )
        otis.assert_has(resp_after_improper, "Submit answers")

        # submit quiz properly
        resp_after_submit = otis.post_20x(
            "quiz",
            alice.pk,
            quiz_waltz.pk,
            data={
                "guess1": "1337",
                "guess2": "2000",
                "guess3": "30+100",  # pretend it's a typo for 30 x 100 I guess
                "guess4": "2^5*5^3",
            },
        )
        otis.assert_has(resp_after_submit, "1337", count=1)
        otis.assert_has(resp_after_submit, "1000", count=1)
        otis.assert_has(resp_after_submit, "2000", count=2)
        otis.assert_has(resp_after_submit, "30+100", count=1)
        otis.assert_has(resp_after_submit, "3000", count=1)
        otis.assert_has(resp_after_submit, "2^5*5^3", count=1)
        otis.assert_has(resp_after_submit, "4000", count=1)
        otis.assert_has(resp_after_submit, "5000", count=1)
        otis.assert_not_has(resp_after_submit, "Submit answers")

        # verify that the attempt is saved properly
        a = ExamAttempt.objects.get(student__user__username="alice")
        assert a.score == 2
        assert a.guess1 == "1337"
        assert a.guess2 == "2000"
        assert a.guess3 == "30+100"
        assert a.guess4 == "2^5*5^3"
        assert a.guess5 == ""

        # refresh the page
        resp_after_refresh = otis.get_ok("quiz", alice.pk, quiz_waltz.pk)
        assert resp_after_submit.content.decode() == resp_after_refresh.content.decode()

        # Try to resubmit the quiz (despite existing submission); should fail
        otis.post_denied("quiz", alice.pk, quiz_waltz.pk, data={"guess1": "7*191"})

        bob = Student.objects.get(user__username="bob")
        otis.login("bob")
        otis.post_denied("quiz", bob.pk, quiz_waltz.pk, data={"answer1": 1337})

    with freeze_time("2022-12-31", tz_offset=0):
        a.delete()  # make sure we can't resubmit
        otis.login("alice")
        otis.post_denied("quiz", alice.pk, quiz_waltz.pk, data={"answer1": 1337})
