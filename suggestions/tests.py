import pytest

from core.factories import GroupFactory, UnitFactory, UnitGroupFactory, UserFactory
from core.models import Unit, UnitGroup
from suggestions.models import ProblemSuggestion


@pytest.mark.django_db
def test_suggestions(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory(username="alice", groups=(verified_group,))
    eve = UserFactory(username="eve", groups=(verified_group,))

    UnitGroupFactory()
    unitgroup: UnitGroup = UnitGroupFactory.create()
    unit: Unit = UnitFactory.create(code=f"B{unitgroup.subject}W", group=unitgroup)

    otis.get_login_redirect("suggest-new", 10)

    otis.login(alice)

    resp = otis.post_20x(
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
    assert (
        "Successfully submitted suggestion! Thanks much :) You can add more using the form below."
        in messages
    )

    otis.assert_has(otis.get_20x("suggest-queue-listing"), "Ring around the Rosie")

    sugg: ProblemSuggestion = ProblemSuggestion.objects.get(user=alice)

    # Update solution
    resp = otis.post_20x(
        "suggest-update",
        sugg.pk,
        data={
            "unit": sugg.unit_id,
            "weight": sugg.weight,
            "source": sugg.source,
            "hyperlink": sugg.hyperlink,
            "description": sugg.description,
            "statement": sugg.statement,
            "solution": (
                "By Cauchy, solution must be of the form $f(x) = cx$, casework on $c$ gives"
                " the answer."
            ),
            "comments": sugg.comments,
            "acknowledge": False,
        },
        follow=True,
    )

    messages = [m.message for m in resp.context["messages"]]
    assert "Edits saved." in messages

    sugg.refresh_from_db()
    assert not sugg.acknowledge

    otis.assert_has(otis.get_20x("suggest-queue-listing"), "Ring around the Rosie")
    otis.assert_has(otis.get_20x("suggest-list"), "Shortlist 1955")

    otis.login(eve)

    otis.assert_has(otis.get_20x("suggest-queue-listing"), "Ring around the Rosie")
    otis.assert_not_has(otis.get_20x("suggest-list"), "Shortlist 1955")
    otis.post_denied("suggest-delete", sugg.pk, follow=True)

    otis.login(alice)

    otis.post_20x("suggest-delete", sugg.pk, follow=True)

    assert not ProblemSuggestion.objects.filter(user=alice).exists()
