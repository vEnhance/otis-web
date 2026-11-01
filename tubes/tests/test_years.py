from datetime import timedelta

import pytest
from django.utils import timezone

from tubes.factories import (
    OIMEProposalFactory,
    OIMESelectionFactory,
    OIMEYearFactory,
)
from tubes.models import OIMEProposal

from .helpers import verified_contributor, verified_staff

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
def test_landing_shows_closed_without_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["accepting_year"] is None
    otis.assert_testid(resp, "proposals-closed-note")


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
