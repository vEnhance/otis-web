import io
import zipfile
from datetime import timedelta

import pytest
from django.contrib.messages import constants as message_levels
from django.utils import timezone

from tubes.factories import (
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
    OIMESelectionFactory,
    OIMEYearFactory,
)
from tubes.models import OIMEProposal, OIMESelection, OIMEYear

from .helpers import verified_admin, verified_contributor, verified_staff

PROPOSAL_DATA = {
    "title": "Squares",
    "statement": "Find all $x$ such that $x^2 = 4$.",
    "answer": 2,
    "solution": "Clearly $x = \\pm 2$.",
    "subject": "A",
    "difficulty": 1,
}


def closed_year(**kwargs):
    """A year whose proposal window closed yesterday."""
    now = timezone.now()
    return OIMEYearFactory.create(
        proposals_open_at=now - timedelta(days=30),
        proposals_close_at=now - timedelta(days=1),
        **kwargs,
    )


def released_year(**kwargs):
    return closed_year(release_at=timezone.now() - timedelta(hours=1), **kwargs)


# ---------------------------------------------------------------------------
# Submission window
# ---------------------------------------------------------------------------


def update_data(**kwargs):
    """Form data for editing a proposal; difficulty is fixed after creation."""
    data = {**PROPOSAL_DATA, **kwargs}
    data.pop("difficulty")
    return data


@pytest.mark.django_db
def test_create_form_defaults_to_draft_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-create")
    assert resp.context["form"].initial["is_draft"] is True


@pytest.mark.django_db
def test_create_published_blocked_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.post("oime-proposal-create", data=PROPOSAL_DATA)
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    assert OIMEProposal.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_allowed_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    otis.post_30x("oime-proposal-create", data={**PROPOSAL_DATA, "is_draft": True})
    assert OIMEProposal.objects.get().is_draft is True


@pytest.mark.django_db
def test_create_allowed_during_window(otis):
    user, _ = verified_contributor()
    OIMEYearFactory.create()
    otis.login(user)
    otis.post_30x("oime-proposal-create", data=PROPOSAL_DATA)
    assert OIMEProposal.objects.get().is_draft is False


@pytest.mark.django_db
def test_staff_may_create_outside_window(otis):
    staff, _ = verified_staff()
    closed_year()
    otis.login(staff)
    otis.post_30x("oime-proposal-create", data=PROPOSAL_DATA)
    assert OIMEProposal.objects.get().is_draft is False


@pytest.mark.django_db
def test_publishing_a_draft_blocked_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update", proposal.pk, data=update_data(is_draft=False)
    )
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    proposal.refresh_from_db()
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_editing_a_draft_allowed_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data(is_draft=True))
    proposal.refresh_from_db()
    assert proposal.title == "Squares"
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_unpublishing_blocked_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=False)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update", proposal.pk, data=update_data(is_draft=True)
    )
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    proposal.refresh_from_db()
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_editing_a_published_problem_allowed_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=False)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data())
    proposal.refresh_from_db()
    assert proposal.title == "Squares"
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_publishing_a_draft_during_window(otis):
    user, contributor = verified_contributor()
    OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data(is_draft=False))
    proposal.refresh_from_db()
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_landing_shows_deadline_when_open(otis):
    user, _ = verified_contributor()
    year = OIMEYearFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["accepting_year"] == year
    otis.assert_testid(resp, "proposals-open-note")


@pytest.mark.django_db
def test_landing_not_accepting_without_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["accepting_year"] is None


# ---------------------------------------------------------------------------
# Pool, freezing and retirement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_in_pool_excludes_only_retired():
    plain = OIMEProposalFactory.create()
    shortlisted = OIMESelectionFactory.create().proposal
    deferred_released = OIMESelectionFactory.create(
        year=released_year(), status="SEL_DEFERRED"
    ).proposal
    retired = OIMESelectionFactory.create(
        year=released_year(), status="SEL_DONE"
    ).proposal
    pool = set(OIMEProposal.in_pool())
    assert {plain, shortlisted, deferred_released} <= pool
    assert retired not in pool
    assert retired.is_retired is True
    assert deferred_released.is_retired is False


@pytest.mark.django_db
def test_retired_problem_is_hidden_and_frozen(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMESelectionFactory.create(
        year=released_year(), proposal__author=other
    ).proposal
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert proposal not in resp.context["proposals"]
    otis.get_40x("oime-proposal-detail", proposal.pk)
    otis.post_40x("oime-start-fight", proposal.pk)


@pytest.mark.django_db
def test_retired_problem_readable_by_author_but_frozen(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(
        year=released_year(), proposal__author=contributor
    ).proposal
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_upvote"] is False
    assert resp.context["can_comment"] is False
    otis.assert_testid(resp, "proposal-retired-note")


@pytest.mark.django_db
def test_selected_problem_locks_author_edits(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(proposal__author=contributor).proposal
    otis.login(user)
    otis.get_40x("oime-proposal-update", proposal.pk)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_edit"] is False
    otis.assert_no_testid(resp, "proposal-edit-link")


@pytest.mark.django_db
def test_deferred_problem_stays_editable(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(
        proposal__author=contributor, status="SEL_DEFERRED"
    ).proposal
    otis.login(user)
    otis.get_20x("oime-proposal-update", proposal.pk)


@pytest.mark.django_db
def test_staff_may_edit_selected_problem(otis):
    staff, _ = verified_staff()
    proposal = OIMESelectionFactory.create().proposal
    otis.login(staff)
    otis.get_20x("oime-proposal-update", proposal.pk)


# ---------------------------------------------------------------------------
# The current year on the front page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_current_year_ignores_unopened_year():
    now = timezone.now()
    editing = closed_year()
    OIMEYearFactory.create(
        proposals_open_at=now + timedelta(days=30),
        proposals_close_at=now + timedelta(days=60),
    )
    assert OIMEYear.current() == editing


@pytest.mark.django_db
def test_current_year_falls_back_to_unopened_year():
    now = timezone.now()
    upcoming = OIMEYearFactory.create(
        proposals_open_at=now + timedelta(days=30),
        proposals_close_at=now + timedelta(days=60),
    )
    assert OIMEYear.current() == upcoming


@pytest.mark.django_db
def test_year_pages_are_admin_only(otis):
    staff, _ = verified_staff()
    year = OIMEYearFactory.create()
    otis.login(staff)
    otis.get_40x("oime-year-detail", year.pk)
    otis.get_40x("oime-year-release", year.pk)
    otis.post_40x(
        "oime-year-triage",
        year.pk,
        data={"proposal": 1, "change_status": "SEL_DEFERRED"},
    )


@pytest.mark.django_db
def test_eic_desk_buckets(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year)
    deferred = OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    unreviewed = OIMEProposalFactory.create()
    OIMEProposalFactory.create(archived=True)
    otis.login(admin)
    resp = otis.get_20x("oime-year-detail", year.pk)
    desk = resp.context["desk"]
    assert desk["year"] == year
    assert desk["chosen_eic"] == [chosen]
    assert desk["deferred_proposals"] == [deferred.proposal]
    assert desk["pool"] == [unreviewed]


@pytest.mark.django_db
def test_eic_desk_splits_on_who_is_blocking(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    shortlisted = OIMESelectionFactory.create(year=year, status="SEL_SHORTLISTED")
    review = OIMESelectionFactory.create(year=year, status="SEL_REVIEW")
    editing = OIMESelectionFactory.create(year=year, status="SEL_EDITING")
    done = OIMESelectionFactory.create(year=year, status="SEL_DONE")
    otis.login(admin)
    desk = otis.get_20x("oime-year-detail", year.pk).context["desk"]
    assert set(desk["chosen_eic"]) == {shortlisted, review}
    assert set(desk["chosen_others"]) == {editing, done}


@pytest.mark.django_db
def test_eic_desk_shows_description(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    OIMESelectionFactory.create(year=year, description="$3n$ and $4n$")
    otis.login(admin)
    resp = otis.get_20x("oime-year-detail", year.pk)
    otis.assert_testid(resp, "chosen-description")
    otis.assert_testid(resp, "year-bulk-edit-link")


@pytest.mark.django_db
def test_eic_desk_pool_sorted_by_votes(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    quiet = OIMEProposalFactory.create()
    popular = OIMEProposalFactory.create()
    popular.upvotes.add(OIMEContributorFactory.create())
    otis.login(admin)
    resp = otis.get_20x("oime-year-detail", year.pk)
    assert resp.context["desk"]["pool"] == [popular, quiet]
    assert resp.context["desk"]["pool"][0].upvote_count == 1


@pytest.mark.django_db
def test_eic_landing_lists_every_year(otis):
    admin, _ = verified_admin()
    older = released_year()
    newer = OIMEYearFactory.create()
    OIMESelectionFactory.create(year=newer)
    OIMESelectionFactory.create(year=newer, status="SEL_DEFERRED")
    otis.login(admin)
    resp = otis.get_20x("oime-landing")
    assert resp.context["years"] == [newer, older]
    assert resp.context["years"][0].chosen_count == 1
    assert "my_selections" not in resp.context
    otis.assert_testid(resp, "year-row", count=2)


@pytest.mark.django_db
def test_nothing_chosen_for_uninvolved_contributor(otis):
    user, _ = verified_contributor()
    OIMESelectionFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert "my_selections" not in resp.context
    otis.assert_no_testid(resp, "current-year")


@pytest.mark.django_db
def test_chosen_for_editor_and_author(otis):
    user, me = verified_contributor()
    year = OIMEYearFactory.create()
    editing = OIMESelectionFactory.create(year=year, editor=me, status="SEL_EDITING")
    authored = OIMESelectionFactory.create(year=year, proposal__author=me)
    OIMESelectionFactory.create(year=year, proposal__author=me, status="SEL_DEFERRED")
    OIMESelectionFactory.create(year=year)
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert set(resp.context["my_selections"]) == {editing, authored}
    assert resp.context["current_year"] == year
    otis.assert_testid(resp, "year-overleaf-link")


@pytest.mark.django_db
def test_triage_from_proposal_page(otis):
    # The EIC browses casually, so problem pages open without a timed session.
    admin, _ = verified_admin(casual_mode=True)
    year = OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_triage"] is True
    otis.assert_testid(resp, "triage-form")

    otis.post_redirects(
        otis.url("oime-year-detail", year.pk),
        "oime-year-triage",
        year.pk,
        data={"proposal": proposal.pk, "change_status": "SEL_SHORTLISTED"},
    )
    selection = OIMESelection.objects.get(year=year, proposal=proposal)
    assert selection.status == "SEL_SHORTLISTED"

    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_triage"] is False
    otis.assert_no_testid(resp, "triage-form")
    otis.assert_testid(resp, "selection-card")

    otis.post_30x(
        "oime-year-triage",
        year.pk,
        data={"proposal": proposal.pk, "change_status": "SEL_DEFERRED"},
    )
    selection.refresh_from_db()
    assert selection.status == "SEL_DEFERRED"
    assert OIMESelection.objects.count() == 1


@pytest.mark.django_db
def test_triage_offers_archive(otis):
    admin, _ = verified_admin(casual_mode=True)
    OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "triage-archive")


@pytest.mark.django_db
def test_triage_moves_to_next_unreviewed(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    current = OIMEProposalFactory.create()
    popular = OIMEProposalFactory.create()
    popular.upvotes.add(OIMEContributorFactory.create())
    OIMEProposalFactory.create()
    otis.login(admin)
    otis.post_redirects(
        otis.url("oime-proposal-detail", popular.pk),
        "oime-year-triage",
        year.pk,
        data={"proposal": current.pk, "change_status": "SEL_DEFERRED"},
    )


@pytest.mark.django_db
def test_triage_archive(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create()
    otis.login(admin)
    otis.post_redirects(
        otis.url("oime-year-detail", year.pk),
        "oime-year-triage",
        year.pk,
        data={"proposal": proposal.pk, "archive": ""},
    )
    proposal.refresh_from_db()
    assert proposal.archived is True
    assert not OIMESelection.objects.exists()


@pytest.mark.django_db
def test_no_triage_for_archived_problem(otis):
    admin, _ = verified_admin(casual_mode=True)
    OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create(archived=True)
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_triage"] is False


@pytest.mark.django_db
def test_editor_sees_overleaf_in_transition_row(otis):
    user, contributor = verified_contributor()
    selection = OIMESelectionFactory.create(status="SEL_EDITING", editor=contributor)
    OIMEFightFactory.create(
        contributor=contributor, proposal=selection.proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    otis.assert_testid(resp, "selection-overleaf")


@pytest.mark.django_db
def test_triage_needs_a_current_year(otis):
    # The EIC browses casually, so problem pages open without a timed session.
    admin, _ = verified_admin(casual_mode=True)
    proposal = OIMEProposalFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_triage"] is False


# ---------------------------------------------------------------------------
# Selection cards: transitions, editor, notes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_eic_transitions_and_jumps(otis):
    # The EIC browses casually, so problem pages open without a timed session.
    admin, _ = verified_admin(casual_mode=True)
    selection = OIMESelectionFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    (card,) = resp.context["selection_cards"]
    assert [t for t, _ in card["transitions"]] == ["SEL_EDITING", "SEL_DEFERRED"]

    otis.post_30x(
        "oime-selection-action", selection.pk, data={"change_status": "SEL_EDITING"}
    )
    selection.refresh_from_db()
    assert selection.status == "SEL_EDITING"
    # Not a suggested transition from Editing, but the EIC may jump anywhere.
    otis.post_30x(
        "oime-selection-action", selection.pk, data={"change_status": "SEL_DONE"}
    )
    selection.refresh_from_db()
    assert selection.status == "SEL_DONE"
    otis.post_40x(
        "oime-selection-action", selection.pk, data={"change_status": "BOGUS"}
    )


@pytest.mark.django_db
def test_eic_assigns_editor_and_notes(otis):
    admin, _ = verified_admin()
    editor = OIMEContributorFactory.create()
    selection = OIMESelectionFactory.create()
    otis.login(admin)
    otis.post_30x(
        "oime-selection-action",
        selection.pk,
        data={
            "save": "1",
            "editor": editor.pk,
            "notes": "go",
            "description": "$3n$ and $4n$",
        },
    )
    selection.refresh_from_db()
    assert selection.editor == editor
    assert selection.notes == "go"
    assert selection.description == "$3n$ and $4n$"


@pytest.mark.django_db
def test_eic_form_only_on_chosen(otis):
    admin, _ = verified_admin(casual_mode=True)
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year)
    deferred = OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    otis.login(admin)
    resp = otis.get_20x("oime-proposal-detail", chosen.proposal.pk)
    (card,) = resp.context["selection_cards"]
    assert card["form"] is not None
    otis.assert_testid(resp, "selection-form")
    resp = otis.get_20x("oime-proposal-detail", deferred.proposal.pk)
    (card,) = resp.context["selection_cards"]
    assert card["form"] is None
    otis.assert_no_testid(resp, "selection-form")


@pytest.mark.django_db
def test_year_admin_hides_deferred(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year)
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    otis.login(admin)
    resp = otis.get_20x("admin:tubes_oimeyear_change", year.pk)
    (inline,) = resp.context["inline_admin_formsets"]
    assert list(inline.formset.queryset) == [chosen]


@pytest.mark.django_db
def test_editor_requests_review_only(otis):
    user, editor = verified_contributor()
    selection = OIMESelectionFactory.create(editor=editor, status="SEL_EDITING")
    # The editor is not the author, so detail is gated on having seen the problem.
    OIMEFightFactory.create(
        contributor=editor, proposal=selection.proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    (card,) = resp.context["selection_cards"]
    assert [t for t, _ in card["transitions"]] == ["SEL_REVIEW"]
    assert card["form"] is None
    otis.assert_testid(resp, "selection-blocked-on")

    otis.post_40x(
        "oime-selection-action", selection.pk, data={"change_status": "SEL_DONE"}
    )
    otis.post_40x(
        "oime-selection-action",
        selection.pk,
        data={"save": "1", "editor": editor.pk, "notes": "mine now"},
    )
    resp = otis.post(
        "oime-selection-action",
        selection.pk,
        data={"change_status": "SEL_REVIEW"},
        follow=True,
    )
    selection.refresh_from_db()
    assert selection.status == "SEL_REVIEW"
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    # While the EIC has the ball, the editor can only pull it back.
    (card,) = resp.context["selection_cards"]
    assert [t for t, _ in card["transitions"]] == ["SEL_EDITING"]


@pytest.mark.django_db
def test_editor_sees_notes(otis):
    user, editor = verified_contributor()
    selection = OIMESelectionFactory.create(
        editor=editor, status="SEL_EDITING", notes="Fix the diagram."
    )
    OIMEFightFactory.create(
        contributor=editor, proposal=selection.proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    otis.assert_testid(resp, "selection-notes")


@pytest.mark.django_db
def test_author_does_not_see_overleaf(otis):
    user, author = verified_contributor()
    selection = OIMESelectionFactory.create(
        proposal=OIMEProposalFactory.create(author=author)
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    otis.assert_testid(resp, "selection-card")
    otis.assert_no_testid(resp, "selection-overleaf")
    resp = otis.get_20x("oime-landing")
    assert resp.context["my_selections"] == [selection]
    assert resp.context["show_overleaf"] is False
    otis.assert_no_testid(resp, "year-overleaf-link")


@pytest.mark.django_db
def test_author_sees_notes(otis):
    user, author = verified_contributor()
    selection = OIMESelectionFactory.create(
        proposal=OIMEProposalFactory.create(author=author), notes="Fix the diagram."
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    otis.assert_testid(resp, "selection-notes")


@pytest.mark.django_db
def test_non_editor_cannot_act_on_selection(otis):
    user, _ = verified_contributor()
    selection = OIMESelectionFactory.create(
        editor=OIMEContributorFactory.create(), status="SEL_EDITING"
    )
    otis.login(user)
    otis.post_40x(
        "oime-selection-action", selection.pk, data={"change_status": "SEL_REVIEW"}
    )
    selection.refresh_from_db()
    assert selection.status == "SEL_EDITING"


@pytest.mark.django_db
def test_selection_card_visibility(otis):
    user, me = verified_contributor()
    selection = OIMESelectionFactory.create(editor=OIMEContributorFactory.create())
    OIMEFightFactory.create(
        contributor=me, proposal=selection.proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    assert resp.context["selection_cards"] == []

    # The author sees the card but gets no buttons.
    mine = OIMESelectionFactory.create(proposal__author=me)
    resp = otis.get_20x("oime-proposal-detail", mine.proposal.pk)
    (card,) = resp.context["selection_cards"]
    assert card["selection"] == mine
    assert card["transitions"] == []
    otis.assert_no_testid(resp, "selection-transition")


@pytest.mark.django_db
def test_author_sees_description(otis):
    user, me = verified_contributor()
    selection = OIMESelectionFactory.create(
        proposal__author=me, description="$3n$ and $4n$"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", selection.proposal.pk)
    otis.assert_testid(resp, "selection-description")


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_release_lists_chosen_and_sets_date(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    done = OIMESelectionFactory.create(year=year, status="SEL_DONE")
    editing = OIMESelectionFactory.create(year=year, status="SEL_EDITING")
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    otis.login(admin)
    resp = otis.get_20x("oime-year-release", year.pk)
    assert set(resp.context["chosen"]) == {done, editing}
    assert resp.context["not_done"] == [editing]
    otis.assert_testid(resp, "release-not-done")

    otis.post_30x("oime-year-release", year.pk, data={"release_at": "2026-12-18T19:00"})
    year.refresh_from_db()
    assert year.release_at is not None
    assert timezone.localtime(year.release_at).strftime("%Y-%m-%d %H:%M") == (
        "2026-12-18 19:00"
    )


@pytest.mark.django_db
def test_release_retires_chosen_problems(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year, status="SEL_DONE").proposal
    deferred = OIMESelectionFactory.create(year=year, status="SEL_DEFERRED").proposal
    otis.login(admin)
    past = timezone.localtime(timezone.now() - timedelta(hours=1))
    otis.post_30x(
        "oime-year-release",
        year.pk,
        data={"release_at": past.strftime("%Y-%m-%dT%H:%M")},
    )
    pool = set(OIMEProposal.in_pool())
    assert chosen not in pool
    assert deferred in pool

    otis.post_30x("oime-year-release", year.pk, data={"clear": "1"})
    year.refresh_from_db()
    assert year.release_at is None
    assert chosen in set(OIMEProposal.in_pool())


# ---------------------------------------------------------------------------
# Exports: the bytes are the product here
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_exports_are_admin_only(otis):
    staff, _ = verified_staff()
    year = OIMEYearFactory.create()
    otis.login(staff)
    otis.get_40x("oime-year-export", year.pk)
    otis.get_40x("oime-year-bulk-edit", year.pk)


@pytest.mark.django_db
def test_export_zip_has_house_format(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    author = OIMEContributorFactory.create(display_name="Jiahe Liu")
    proposal = OIMEProposalFactory.create(
        author=author,
        subject="C",
        title="i <3 u",
        statement="Count pairs.",
        answer=41,
        solution="Use Pick's theorem.",
    )
    OIMESelectionFactory.create(
        year=year, proposal=proposal, status="SEL_DONE", description="$i <3 u$"
    )
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    solver = OIMEContributorFactory.create(display_name="Tester Ann")
    OIMEFightFactory.create(contributor=solver, proposal=proposal, status="OIME_OK")
    # An unfinished fight on some other problem must not drop a testsolver.
    OIMEFightFactory.create(contributor=solver, status="OIME_TBD")
    bystander = OIMEContributorFactory.create(display_name="Only Started")
    OIMEFightFactory.create(contributor=bystander, proposal=proposal, status="OIME_TBD")
    shy = OIMEContributorFactory.create(
        display_name="Shy Solver", hide_from_acknowledgments=True
    )
    OIMEFightFactory.create(contributor=shy, proposal=proposal, status="OIME_OK")

    otis.login(admin)
    resp = otis.get_20x("oime-year-export", year.pk)
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    assert sorted(archive.namelist()) == [
        "data/solves.tex",
        "data/testsolving.tex",
        f"originals/{proposal.label}.tex",
        f"problems/{proposal.label}.tex",
        "problems/acknow.tex",
        "problems/order1.tex",
    ]
    tex = archive.read(f"problems/{proposal.label}.tex").decode()
    assert (
        "\\shortdesc{$i <3 u$}\n\\begin{problem}\n  Count pairs.\n\\end{problem}" in tex
    )
    assert "\\answer{041}" in tex
    assert "\\credits{Jiahe Liu}" in tex
    assert "\\begin{soln}\n  Use Pick's theorem.\n\\end{soln}" in tex
    assert otis.url("oime-proposal-detail", proposal.pk) in tex

    order = archive.read("problems/order1.tex").decode()
    assert f"\\input{{problems/{proposal.label}}}  % [C] $i <3 u$" in order
    assert archive.read(f"originals/{proposal.label}.tex") == b"Count pairs.\n"

    acknow = archive.read("problems/acknow.tex").decode()
    assert "Jiahe Liu," in acknow
    assert "Tester Ann,  % 1 problems" in acknow
    assert "Shy Solver" not in acknow
    assert "Only Started" not in acknow


@pytest.mark.django_db
def test_export_description_defaults_to_escaped_title(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create(title="50% off")
    OIMESelectionFactory.create(year=year, proposal=proposal)
    otis.login(admin)
    archive = zipfile.ZipFile(
        io.BytesIO(otis.get_20x("oime-year-export", year.pk).content)
    )
    tex = archive.read(f"problems/{proposal.label}.tex").decode()
    assert "\\shortdesc{50\\% off}" in tex


@pytest.mark.django_db
def test_export_stats(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    solved = OIMEProposalFactory.create()
    unsolved = OIMEProposalFactory.create()
    OIMESelectionFactory.create(year=year, proposal=solved)
    OIMESelectionFactory.create(year=year, proposal=unsolved)
    fast = OIMEFightFactory.create(proposal=solved, status="OIME_OK")
    fast.submitted_at = fast.started_at + timedelta(seconds=75)
    fast.save()
    slow = OIMEFightFactory.create(proposal=solved, status="OIME_OK")
    solved.upvotes.add(slow.contributor)
    slow.submitted_at = slow.started_at + timedelta(seconds=125)
    slow.save()
    OIMEFightFactory.create(
        proposal=solved, status="OIME_OK", wrong_answers=1, submitted_at=timezone.now()
    )
    OIMEFightFactory.create(proposal=solved, status="OIME_FAIL")
    OIMEFightFactory.create(proposal=unsolved, status="OIME_FAIL")

    otis.login(admin)
    archive = zipfile.ZipFile(
        io.BytesIO(otis.get_20x("oime-year-export", year.pk).content)
    )
    stats = archive.read("data/testsolving.tex").decode()
    assert (
        f"\\oimetestsolving{{{solved.label}}}{{1:15}}{{1:40}}{{2}}{{3}}{{4}}{{1}}"
        in stats
    )
    assert (
        f"\\oimetestsolving{{{unsolved.label}}}{{---}}{{---}}{{0}}{{0}}{{1}}{{0}}"
        in stats
    )
    solves = archive.read("data/solves.tex").decode()
    assert f"%\\oimesolves{{{solved.label}}}{{}}" in solves
    assert "%\\oimescore{2}{}" in solves


@pytest.mark.django_db
def test_bulk_edit_lists_only_chosen(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year)
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    OIMESelectionFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-year-bulk-edit", year.pk)
    assert [f.instance for f in resp.context["formset"]] == [chosen]


@pytest.mark.django_db
def test_bulk_edit_bulk_save(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    first = OIMESelectionFactory.create(year=year)
    second = OIMESelectionFactory.create(year=year, description="old")
    editor = OIMEContributorFactory.create()
    otis.login(admin)
    otis.post_redirects(
        otis.url("oime-year-bulk-edit", year.pk),
        "oime-year-bulk-edit",
        year.pk,
        data={
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-0-id": str(first.pk),
            "form-0-editor": str(editor.pk),
            "form-0-description": "$3n$ and $4n$",
            "form-1-id": str(second.pk),
            "form-1-description": "",
        },
    )
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.description == "$3n$ and $4n$"
    assert first.editor == editor
    assert second.description == ""
