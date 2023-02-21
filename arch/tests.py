import os

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from arch.factories import ProblemFactory
from arch.models import Hint, Problem, Vote
from core.factories import GroupFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase


class TestProblem(EvanTestCase):
    @override_settings(
        PATH_STATEMENT_ON_DISK=os.path.join(settings.BASE_DIR, "test_static/")
    )
    def test_disk_problem(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(groups=(verified_group,))
        self.login(alice)

        disk_puid = "STUPID"

        if not os.path.exists(settings.PATH_STATEMENT_ON_DISK):
            os.makedirs(settings.PATH_STATEMENT_ON_DISK)

        problem_path = os.path.join(
            settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.html"
        )

        with open(problem_path, "w") as f:
            f.write("rock and roll")

        self.assertGet40X(
            "hint-list",
            disk_puid,
        )

        self.assertGet40X(
            "hint-list",
            "invalid-",
        )

        resp = self.assertGet20X(
            "hint-list-check",
            disk_puid,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(f"Created previously nonexistent problem {disk_puid}", messages)

        self.assertContains(resp, "rock and roll")

        os.remove(problem_path)
        if not os.listdir(settings.PATH_STATEMENT_ON_DISK):
            os.rmdir(settings.PATH_STATEMENT_ON_DISK)

    def test_problem(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(groups=(verified_group,))
        self.login(alice)

        problem: Problem = ProblemFactory.create(puid="SILLY")

        self.assertPost20X(
            "arch-index",
            data={"puid": problem.puid, "hyperlink": "https://otis.evanchen.cc/"},
            follow=True,
        )

        problem = Problem.objects.filter(puid=problem.puid).first()

        self.assertPost20X(
            "problem-update",
            problem.puid,
            data={"puid": "SILLIER", "hyperlink": "https://artofproblemsolving.com/"},
            follow=True,
        )
        self.assertContains(
            self.assertGet20X(
                "problem-update",
                "SILLIER",
            ),
            "https://artofproblemsolving.com/",
        )

        problem.refresh_from_db()
        self.assertTrue(problem.puid == "SILLIER")

    def test_hint(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(groups=(verified_group,))
        self.login(alice)

        problem: Problem = ProblemFactory.create()

        self.assertGet20X(
            "hint-list",
            problem.puid,
        )
        self.assertGet40X("hint-detail", problem.pk, 31)

        self.assertContains(
            self.assertGet20X(
                "hint-create",
                problem.puid,
            ),
            "Advice for writing hints",
        )
        self.assertPost20X(
            "hint-create",
            problem.puid,
            data={
                "problem": problem.pk,
                "number": 31,
                "keywords": "keywords or something",
                "content": "just solve it",
            },
            follow=True,
        )

        hint: Hint = Hint.objects.filter(problem=problem).first()

        resp = self.assertGet20X("hint-detail", problem.puid, 31)
        self.assertContains(resp, hint.content)

        self.assertGet40X("hint-detail", problem.puid, 41)
        self.assertGet20X("hint-detail-pk", hint.pk)
        self.assertContains(
            self.assertGet20X(
                "hint-update",
                problem.puid,
                31,
            ),
            hint.keywords,
        )
        self.assertPost20X(
            "hint-update",
            problem.puid,
            31,
            data={
                "problem": hint.problem.pk,
                "number": 41,
                "keywords": hint.keywords,
                "content": hint.content,
                "reason": "Changed number",
            },
            follow=True,
        )

        self.assertGet40X("hint-detail", problem.puid, 31)
        resp = self.assertGet20X("hint-detail", problem.puid, 41)

        self.assertContains(
            self.assertGet20X(
                "hint-update-pk",
                hint.pk,
            ),
            hint.keywords,
        )
        self.assertPost20X(
            "hint-update-pk",
            hint.pk,
            data={
                "problem": hint.problem.pk,
                "number": 51,
                "keywords": hint.keywords,
                "content": hint.content,
                "reason": "Changed number again",
            },
            follow=True,
        )

        self.assertGet40X("hint-detail", problem.puid, 41)
        self.assertGet20X("hint-detail", problem.puid, 51)

        self.assertPost20X("hint-delete", problem.puid, 51, follow=True)

        self.assertFalse(Hint.objects.filter(problem=problem).exists())

    def test_vote(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(groups=(verified_group,))
        self.login(alice)

        problem: Problem = ProblemFactory.create()

        self.assertGet20X("vote-create", problem.puid)

        resp = self.assertPost20X(
            "vote-create",
            problem.puid,
            data={
                "niceness": 4,
            },
            follow=True,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(f"You rated {problem.puid} as 4.", messages)

        self.assertTrue(Vote.objects.filter(problem__puid=problem.puid).exists())

    def test_lookup(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(groups=(verified_group,))
        self.login(alice)

        problem: Problem = ProblemFactory.create()

        self.assertGetRedirects(
            reverse("arch-index"),
            "arch-lookup",
        )

        self.assertPostRedirects(
            problem.get_absolute_url(), "arch-lookup", data={"problem": problem.pk}
        )

    def test_view_solution(self):
        alice = UserFactory.create()
        self.login(alice)

        problem: Problem = ProblemFactory.create()

        self.assertGet40X("view-solution", problem.puid)

        # setting up default storage seems like a pain
