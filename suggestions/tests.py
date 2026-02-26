import pytest

from arch.models import User
from core.factories import GroupFactory, UnitFactory, UnitGroupFactory, UserFactory
from core.models import Unit, UnitGroup
from suggestions.factories import ProblemSuggestionFactory
from suggestions.models import ProblemSuggestion


@pytest.mark.django_db
def test_suggestions(otis):
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory(username="alice", groups=(verified_group,))
    eve: User = UserFactory(username="eve", groups=(verified_group,))

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


@pytest.mark.django_db
def test_suggestion_update_ownership(otis):
    """Non-owner cannot overwrite another user's suggestion via POST."""
    alice: User = UserFactory(username="alice")
    eve: User = UserFactory(username="eve")

    UnitGroupFactory()
    unitgroup: UnitGroup = UnitGroupFactory.create()
    unit: Unit = UnitFactory.create(code=f"B{unitgroup.subject}W", group=unitgroup)

    valid_data = {
        "unit": unit.pk,
        "weight": 2,
        "source": "ISL 2020 C5",
        "hyperlink": "",
        "description": "Combinatorics problem",
        "statement": "Find all functions",
        "solution": "Alice original solution",
        "comments": "",
        "acknowledge": True,
    }

    sugg: ProblemSuggestion = ProblemSuggestionFactory(
        user=alice, unit=unit, source="ISL 2020 C5", description="Combinatorics problem"
    )

    # Eve tries to GET Alice's suggestion — should be denied
    otis.login(eve)
    otis.get_denied("suggest-update", sugg.pk)

    # Eve tries to POST to overwrite Alice's suggestion — should be denied
    otis.post_denied(
        "suggest-update",
        sugg.pk,
        data={**valid_data, "solution": "Overwritten by Eve"},
    )

    # Verify the suggestion was NOT modified in the database
    sugg.refresh_from_db()
    assert sugg.solution != "Overwritten by Eve"
    assert sugg.user == alice

    # Alice can still update her own suggestion
    otis.login(alice)
    resp = otis.post_20x(
        "suggest-update",
        sugg.pk,
        data={**valid_data, "solution": "Updated by Alice"},
        follow=True,
    )
    otis.assert_message(resp, "Edits saved.")

    sugg.refresh_from_db()
    assert sugg.solution == "Updated by Alice"
