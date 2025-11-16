from arch.models import User
from core.factories import GroupFactory, UnitFactory, UnitGroupFactory, UserFactory
from core.models import Unit, UnitGroup
from otisweb_testsuite import EvanTestCase
from suggestions.models import ProblemSuggestion


class TestSuggestion(EvanTestCase):
    def test_suggestions(self):
        verified_group = GroupFactory(name="Verified")
        alice: User = UserFactory(username="alice", groups=(verified_group,))
        eve: User = UserFactory(username="eve", groups=(verified_group,))

        UnitGroupFactory()
        unitgroup: UnitGroup = UnitGroupFactory.create()
        unit: Unit = UnitFactory.create(code=f"B{unitgroup.subject}W", group=unitgroup)

        self.assertGetBecomesLoginRedirect("suggest-new", 10)

        self.login(alice)

        resp = self.assertPost20X(
            "suggest-new",
            unit.pk,
            data={
                "unit": unit.pk,
                "weight": 2,
                "source": "Shortlist 1955",
                "hyperlink": "https://math.stackexchange.com/questions/2298446/a-ring-homomorphism-over-rational-numbers-is-the-identity/",
                "description": "Ring around the Rosie",
                "statement": "Find all ring homomorphism over rationals",
                "solution": "This is trivially the identity",
                "comments": "Fun problem",
                "acknowledge": True,
            },
            follow=True,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(
            "Successfully submitted suggestion! Thanks much :) You can add more using the form below.",
            messages,
        )

        self.assertContains(
            self.assertGet20X("suggest-queue-listing"), "Ring around the Rosie"
        )

        sugg: ProblemSuggestion = ProblemSuggestion.objects.get(user=alice)

        # Update solution
        resp = self.assertPost20X(
            "suggest-update",
            sugg.pk,
            data={
                "unit": sugg.unit.pk,
                "weight": sugg.weight,
                "source": sugg.source,
                "hyperlink": sugg.hyperlink,
                "description": sugg.description,
                "statement": sugg.statement,
                "solution": "By Cauchy, solution must be of the form $f(x) = cx$, casework on $c$ gives the answer.",
                "comments": sugg.comments,
                "acknowledge": False,
            },
            follow=True,
        )

        messages = [m.message for m in resp.context["messages"]]
        self.assertIn(
            "Edits saved.",
            messages,
        )

        sugg.refresh_from_db()
        self.assertFalse(sugg.acknowledge)

        self.assertContains(
            self.assertGet20X("suggest-queue-listing"), "Ring around the Rosie"
        )
        self.assertContains(self.assertGet20X("suggest-list"), "Shortlist 1955")

        self.login(eve)

        self.assertContains(
            self.assertGet20X("suggest-queue-listing"), "Ring around the Rosie"
        )
        self.assertNotContains(self.assertGet20X("suggest-list"), "Shortlist 1955")
        self.assertPostDenied("suggest-delete", sugg.pk, follow=True)

        self.login(alice)

        self.assertPost20X("suggest-delete", sugg.pk, follow=True)

        self.assertFalse(ProblemSuggestion.objects.filter(user=alice).exists())
