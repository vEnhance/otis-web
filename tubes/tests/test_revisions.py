from datetime import timedelta

import pytest
from django.utils import timezone

from tubes.factories import (
    OIMEFightFactory,
    OIMEProposalFactory,
    OIMESelectionFactory,
    OIMEYearFactory,
)
from tubes.models import OIMEProposal, OIMESelection

from .helpers import verified_admin, verified_contributor


def edit_data(proposal: OIMEProposal, **kwargs):
    """Form data that resubmits ``proposal`` as it is, plus ``kwargs``."""
    return {
        "title": proposal.title,
        "statement": proposal.statement,
        "answer": proposal.answer,
        "solution": proposal.solution,
        "subject": proposal.subject,
        "difficulty": proposal.difficulty,
        **kwargs,
    }


def revised_before(proposal: OIMEProposal, fight_age: timedelta) -> None:
    """Pretend ``proposal`` was revised after its existing fights started."""
    proposal.fights.update(started_at=timezone.now() - fight_age)
    proposal.revised_at = timezone.now() - fight_age / 2
    proposal.save(update_fields=["revised_at"])


@pytest.mark.django_db
def test_create_form_has_no_breaking_change(otis):
    user, _ = verified_contributor()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-create")
    assert "breaking_change" not in resp.context["form"].fields


@pytest.mark.django_db
def test_edit_without_breaking_change_keeps_version(otis):
    user, me = verified_contributor()
    proposal = OIMEProposalFactory.create(author=me, archived=True)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=edit_data(proposal))
    proposal.refresh_from_db()
    assert proposal.revised_at is None
    assert proposal.archived is True


@pytest.mark.django_db
def test_breaking_change_resubmits_archived_problem(otis):
    user, me = verified_contributor()
    proposal = OIMEProposalFactory.create(author=me, archive_reason="ROUGH")
    otis.login(user)
    otis.post_30x(
        "oime-proposal-update",
        proposal.pk,
        data=edit_data(proposal, breaking_change="on"),
    )
    proposal.refresh_from_db()
    assert proposal.revised_at is not None
    assert proposal.archived is False
    assert proposal in OIMEProposal.in_pool()


@pytest.mark.django_db
def test_breaking_change_returns_deferral_to_triage(otis):
    user, me = verified_contributor()
    year = OIMEYearFactory.create()
    deferred = OIMESelectionFactory.create(
        year=year, proposal__author=me, status="SEL_DEFERRED"
    )
    old_year = OIMEYearFactory.create(
        proposals_open_at=timezone.now() - timedelta(days=400),
        proposals_close_at=timezone.now() - timedelta(days=370),
    )
    old = OIMESelectionFactory.create(
        year=old_year, proposal=deferred.proposal, status="SEL_DEFERRED"
    )
    otis.login(user)
    otis.post_30x(
        "oime-proposal-update",
        deferred.proposal.pk,
        data=edit_data(deferred.proposal, breaking_change="on"),
    )
    assert list(OIMESelection.objects.all()) == [old]


@pytest.mark.django_db
def test_difficulty_change_requires_breaking_change(otis):
    user, me = verified_contributor()
    proposal = OIMEProposalFactory.create(author=me, difficulty=2)
    otis.login(user)
    resp = otis.post_20x(
        "oime-proposal-update", proposal.pk, data=edit_data(proposal, difficulty=4)
    )
    assert "breaking_change" in resp.context["form"].errors
    proposal.refresh_from_db()
    assert proposal.difficulty == 2

    otis.post_30x(
        "oime-proposal-update",
        proposal.pk,
        data=edit_data(proposal, difficulty=4, breaking_change="on"),
    )
    proposal.refresh_from_db()
    assert proposal.difficulty == 4
    assert proposal.revised_at is not None


@pytest.mark.django_db
def test_stats_count_only_the_current_version(otis):
    user, me = verified_contributor()
    proposal = OIMEProposalFactory.create(author=me)
    OIMEFightFactory.create_batch(2, proposal=proposal, status="OIME_FAIL")
    revised_before(proposal, timedelta(hours=2))
    OIMEFightFactory.create(proposal=proposal, status="OIME_OK")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["stats"]["total"] == 1
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    assert len(resp.context["fights"]) == 1


@pytest.mark.django_db
def test_desk_stats_count_only_the_current_version(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create_batch(2, proposal=proposal, status="OIME_FAIL")
    revised_before(proposal, timedelta(hours=2))
    OIMEFightFactory.create(proposal=proposal, status="OIME_OK")
    otis.login(admin)
    (row,) = otis.get_20x("oime-year-detail", year.pk).context["desk"]["pool"]
    assert row.stats["total"] == 1


@pytest.mark.django_db
def test_earlier_version_still_spoils(otis):
    user, me = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(contributor=me, proposal=proposal, status="OIME_FAIL")
    revised_before(proposal, timedelta(hours=2))
    otis.login(user)
    otis.get_30x("oime-start-fight", proposal.pk)
