import datetime

from django.test.utils import override_settings
from django.utils import timezone
from freezegun import freeze_time

from core.factories import SemesterFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase
from exams.calculator import expr_compute
from exams.factories import QuizFactory, TestFactory
from exams.models import ExamAttempt, MockCompleted, PracticeExam
from roster.factories import StudentFactory
from roster.models import Student

UTC = timezone.utc


class ArithmeticTest(EvanTestCase):
    def checkCalculator(self, expr: str, out: float):
        v = expr_compute(expr)
        assert v is not None
        self.assertAlmostEqual(v, out)

    def test_arithmetic(self):
        self.checkCalculator("1/3^4", 1 / 81)
        self.checkCalculator("sin(pi)", 0)
        self.checkCalculator("sqrt(1/2)-cos(pi/4)", 0)
        self.checkCalculator("(2*sqrt(2))^2 - 4^(3/2)", 0)
        self.checkCalculator("16900/4*pi", 13273.2289614)

    def test_pdf(self):
        pass


class ExamTest(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.semester = SemesterFactory(active=True, exam_family="Waltz")
        cls.semester_old = SemesterFactory(active=False, exam_family="Waltz")
        cls.alice = StudentFactory.create(
            user__username="alice",
            semester=cls.semester,
            user__first_name="Alice",
            user__last_name="Aardvark",
        )
        cls.bob = StudentFactory.create(
            user__username="bob",
            semester=cls.semester_old,
            user__first_name="Bob",
            user__last_name="Beta",
        )
        cls.dead = StudentFactory.create(
            user__username="dead",
            enabled=False,
            semester=cls.semester,
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

    def test_exam_pdf(self):
        exam_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
        exam_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

        with freeze_time("2018-01-01", tz_offset=0):
            self.login("alice")
            self.assertGetDenied("exam-pdf", exam_waltz.pk)
            self.assertGetDenied("exam-pdf", exam_foxtrot.pk)
        with freeze_time("2020-06-05", tz_offset=0):
            self.login("alice")
            self.assertGet20X("exam-pdf", exam_waltz.pk)
            self.assertGetDenied("exam-pdf", exam_foxtrot.pk)
        with freeze_time("2022-12-31", tz_offset=0):
            self.login("alice")
            self.assertGet20X("exam-pdf", exam_waltz.pk)
            self.assertGetDenied("exam-pdf", exam_foxtrot.pk)

        with freeze_time("2020-06-05", tz_offset=0):
            self.login("dead")
            self.assertGetDenied("exam-pdf", exam_waltz.pk)
            self.assertGetDenied("exam-pdf", exam_foxtrot.pk)

        staff = UserFactory.create(is_staff=True)
        with freeze_time("2018-01-01", tz_offset=0):
            self.login(staff)
            self.assertGet20X("exam-pdf", exam_waltz.pk)
            self.assertGet20X("exam-pdf", exam_foxtrot.pk)
        with freeze_time("2020-06-05", tz_offset=0):
            self.login(staff)
            self.assertGet20X("exam-pdf", exam_waltz.pk)
            self.assertGet20X("exam-pdf", exam_foxtrot.pk)
        with freeze_time("2022-12-31", tz_offset=0):
            self.login(staff)
            self.assertGet20X("exam-pdf", exam_waltz.pk)
            self.assertGet20X("exam-pdf", exam_foxtrot.pk)

    def test_quiz(self):
        quiz_waltz = PracticeExam.objects.get(family="Waltz", is_test=False)
        quiz_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=False)
        test_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
        test_foxtrot = PracticeExam.objects.get(family="Foxtrot", is_test=True)

        with freeze_time("2018-01-01", tz_offset=0):
            self.login("alice")
            self.assertGetDenied("quiz", ExamTest.alice.pk, quiz_waltz.pk)
            self.assertGetDenied("quiz", ExamTest.alice.pk, test_waltz.pk)
            self.assertGetDenied("quiz", ExamTest.alice.pk, test_foxtrot.pk)
            self.assertGetDenied("quiz", ExamTest.alice.pk, quiz_foxtrot.pk)
        with freeze_time("2020-06-05", tz_offset=0):
            self.login("dead")
            self.assertGetDenied(
                "quiz", Student.objects.get(user__username="dead").pk, quiz_waltz.pk
            )
            self.login("alice")
            self.assertGetDenied("quiz", ExamTest.alice.pk, test_waltz.pk)
            self.assertGetDenied("quiz", ExamTest.alice.pk, test_foxtrot.pk)
            self.assertGetDenied("quiz", ExamTest.alice.pk, quiz_foxtrot.pk)

            # OK, now actually take a quiz, lol
            resp_before_submit = self.assertGet20X(
                "quiz", ExamTest.alice.pk, quiz_waltz.pk
            )
            self.assertHas(resp_before_submit, "Submit answers")

            # submit quiz improperly
            resp_after_improper = self.assertPost20X(
                "quiz",
                ExamTest.alice.pk,
                quiz_waltz.pk,
                data={
                    "guess1": r"$@#%$@#\^__meow__^%&*(==",
                    "guess2": "2000",
                },
            )
            self.assertHas(resp_after_improper, "Submit answers")

            # submit quiz properly
            resp_after_submit = self.assertPost20X(
                "quiz",
                ExamTest.alice.pk,
                quiz_waltz.pk,
                data={
                    "guess1": "1337",
                    "guess2": "2000",
                    "guess3": "30+100",  # pretend it's a typo or 30 x 100 I guess
                    "guess4": "2^5*5^3",
                },
            )
            self.assertHas(resp_after_submit, "1337", count=1)
            self.assertHas(resp_after_submit, "1000", count=1)
            self.assertHas(resp_after_submit, "2000", count=2)
            self.assertHas(resp_after_submit, "30+100", count=1)
            self.assertHas(resp_after_submit, "3000", count=1)
            self.assertHas(resp_after_submit, "2^5*5^3", count=1)
            self.assertHas(resp_after_submit, "4000", count=1)
            self.assertHas(resp_after_submit, "5000", count=1)
            self.assertNotHas(resp_after_submit, "Submit answers")

            # verify that the attempt is saved properly
            a = ExamAttempt.objects.get(student__user__username="alice")
            self.assertEqual(a.score, 2)
            self.assertEqual(a.guess1, "1337")
            self.assertEqual(a.guess2, "2000")
            self.assertEqual(a.guess3, "30+100")
            self.assertEqual(a.guess4, "2^5*5^3")
            self.assertEqual(a.guess5, "")

            # refresh the page
            resp_after_refresh = self.assertGetOK(
                "quiz", ExamTest.alice.pk, quiz_waltz.pk
            )
            self.assertHTMLEqual(
                resp_after_submit.content.decode(),
                resp_after_refresh.content.decode(),
            )

            # Try to resubmit the quiz (despite existing submission); should fail
            self.assertPostDenied(
                "quiz", ExamTest.alice.pk, quiz_waltz.pk, data={"guess1": "7*191"}
            )

            bob = Student.objects.get(user__username="bob")
            self.login("bob")
            self.assertPostDenied("quiz", bob.pk, quiz_waltz.pk, data={"answer1": 1337})

        with freeze_time("2022-12-31", tz_offset=0):
            a.delete()  # make sure we can't resubmit
            self.login("alice")
            self.assertPostDenied(
                "quiz", ExamTest.alice.pk, quiz_waltz.pk, data={"answer1": 1337}
            )

    def test_mocks(self):
        self.login("alice")
        resp = self.assertGet20X("mocks", follow=True)
        self.assertHas(resp, "Waltz Test 01")

        self.login("bob")
        self.assertGetDenied("mocks", ExamTest.bob.pk, follow=True)

        self.login("dead")
        self.assertGetDenied("mocks", follow=True)

    def test_participation_points(self):
        test_waltz = PracticeExam.objects.get(family="Waltz", is_test=True)
        quiz_waltz = PracticeExam.objects.get(family="Waltz", is_test=False)
        # first check that plebians can't login
        self.assertGetBecomesStaffRedirect("participation-points")
        self.assertPostBecomesStaffRedirect("participation-points")
        self.login("alice")
        self.assertGetBecomesStaffRedirect("participation-points")
        self.assertPostBecomesStaffRedirect("participation-points")

        admin = UserFactory.create(is_staff=True, is_superuser=True)
        self.login(admin)
        students = StudentFactory.create_batch(10, semester=ExamTest.semester)
        pks = [str(s.pk) for s in students]

        self.assertGetOK("participation-points")
        # invalid post
        self.assertHas(
            self.assertPostOK("participation-points", data={"pks": "9001"}),
            "This field is required",
        )
        self.assertEqual(MockCompleted.objects.all().count(), 0)
        self.assertHas(
            self.assertPostOK(
                "participation-points", data={"exam": quiz_waltz.pk, "pks": "9001"}
            ),
            "Select a valid choice",
        )
        self.assertEqual(MockCompleted.objects.all().count(), 0)

        resp1 = self.assertPostOK(
            "participation-points",
            data={"exam": test_waltz.pk, "pks": "\n".join(pks[:4])},
        )
        self.assertHas(resp1, "Created 4 completion database entries")
        self.assertNotHas(resp1, "with existing entries")
        self.assertEqual(MockCompleted.objects.all().count(), 4)

        resp2 = self.assertPostOK(
            "participation-points",
            data={"exam": test_waltz.pk, "pks": "\n".join(pks[2:7])},
        )
        self.assertHas(resp2, "Created 3 completion database entries")
        self.assertHas(resp2, "There were 2 students with existing entries")
        self.assertEqual(MockCompleted.objects.all().count(), 7)
