from datetime import timedelta

import pytest
from django.contrib.messages import constants as message_levels
from django.utils import timezone

from tubes.factories import (
    OIMEFightFactory,
    OIMEProposalFactory,
)
from tubes.models import OIMEComment, OIMEFight
from tubes.views import GIVE_UP_RATE_LIMIT, GIVE_UP_WINDOW_MINUTES

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Timed solve flow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unspoiled_start_creates_attempt(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert OIMEFight.objects.filter(contributor=contributor, proposal=proposal).exists()


@pytest.mark.django_db
def test_cannot_start_second_concurrent_fight(otis):
    user, contributor = verified_contributor()
    proposal1 = OIMEProposalFactory.create()
    proposal2 = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal1, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal2.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=proposal2
    ).exists()


@pytest.mark.django_db
def test_correct_answer_solves(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-submit-answer", proposal.pk, data={"answer": 42})
    otis.assert_30x(resp)
    fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
    assert fight.status == "OIME_OK"
    assert fight.submitted_at is not None


@pytest.mark.django_db
def test_wrong_answer_increments_count(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    otis.post("oime-submit-answer", proposal.pk, data={"answer": 99})
    fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
    assert fight.status == "OIME_TBD"
    assert fight.wrong_answers == 1


@pytest.mark.django_db
def test_give_up(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-give-up", proposal.pk)
    otis.assert_30x(resp)
    fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
    assert fight.status == "OIME_FAIL"
    assert fight.submitted_at is not None


@pytest.mark.django_db
def test_give_up_rate_limited(otis):

    user, contributor = verified_contributor()
    proposals = [OIMEProposalFactory.create() for _ in range(GIVE_UP_RATE_LIMIT + 1)]
    recent = timezone.now() - timedelta(minutes=GIVE_UP_WINDOW_MINUTES - 1)
    for p in proposals[:GIVE_UP_RATE_LIMIT]:
        OIMEFightFactory.create(
            contributor=contributor, proposal=p, status="OIME_FAIL", submitted_at=recent
        )
    target = proposals[GIVE_UP_RATE_LIMIT]
    OIMEFightFactory.create(contributor=contributor, proposal=target, status="OIME_TBD")
    otis.login(user)
    resp = otis.post("oime-give-up", target.pk)
    otis.assert_30x(resp)
    target_fight = OIMEFight.objects.get(contributor=contributor, proposal=target)
    assert target_fight.status == "OIME_TBD"


@pytest.mark.django_db
def test_gave_up_sees_solution(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_see_solution"]


@pytest.mark.django_db
def test_cannot_comment_during_active_fight(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    # In-progress attempt → redirected to fight view, never reaches comment form
    resp = otis.post(
        "oime-proposal-detail",
        proposal.pk,
        data={"submit_comment": "1", "content": "Spoiler!"},
    )
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/fight/")
    assert not OIMEComment.objects.exists()


@pytest.mark.django_db
def test_casual_cannot_start_attempt(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


@pytest.mark.django_db
def test_author_cannot_start_attempt(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


# ---------------------------------------------------------------------------
# Ending a timed session: caching, and the give-up/time-out boundary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fight_page_is_not_cacheable(otis):
    # Otherwise "back" after giving up restores the page with a live countdown,
    # which reads as though the attempt were still open.
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-fight", proposal.pk)
    assert "no-store" in resp.headers["Cache-Control"]


@pytest.mark.django_db
def test_give_up_after_time_expired_records_tle(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(difficulty=1)
    fight = OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    OIMEFight.objects.filter(pk=fight.pk).update(
        started_at=timezone.now() - timedelta(hours=5)
    )
    otis.login(user)
    resp = otis.post("oime-give-up", proposal.pk)
    otis.assert_30x(resp)
    fight.refresh_from_db()
    assert fight.status == "OIME_TLE"
    # TLE fights report no solve time, rather than a bogus multi-hour one.
    assert fight.time_display == ""


@pytest.mark.django_db
def test_expired_give_up_does_not_count_against_rate_limit(otis):

    user, contributor = verified_contributor()
    expired = OIMEProposalFactory.create(difficulty=1)
    fight = OIMEFightFactory.create(
        contributor=contributor, proposal=expired, status="OIME_TBD"
    )
    OIMEFight.objects.filter(pk=fight.pk).update(
        started_at=timezone.now() - timedelta(hours=5)
    )
    otis.login(user)
    otis.post("oime-give-up", expired.pk)
    assert (
        OIMEFight.objects.filter(contributor=contributor, status="OIME_FAIL").count()
        < GIVE_UP_RATE_LIMIT
    )


@pytest.mark.django_db
def test_detail_stats_show_own_verdict(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "stats-your-result")
    otis.assert_testid(resp, "verdict-gave-up")


@pytest.mark.django_db
def test_detail_stats_show_dash_when_never_fought(otis):
    """An author never fights their own problem, so their verdict row stays empty."""
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "stats-your-result")
    otis.assert_no_testid(resp, "verdict-gave-up")
    otis.assert_no_testid(resp, "verdict-solved")


@pytest.mark.django_db
def test_results_stats_show_own_verdict(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    assert resp.context["fight"].status == "OIME_OK"
    otis.assert_testid(resp, "stats-your-result")


# ---------------------------------------------------------------------------
# A started session survives the problem or the mode changing underneath it
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_fight_survives_proposal_going_to_draft(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    proposal.is_draft = True
    proposal.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-fight", proposal.pk)
    assert any(m.level == message_levels.WARNING for m in resp.context["messages"])
    # ...and the session can still be closed out normally.
    otis.assert_30x(otis.post("oime-submit-answer", proposal.pk, data={"answer": 42}))
    assert (
        OIMEFight.objects.get(contributor=contributor, proposal=proposal).status
        == "OIME_OK"
    )


@pytest.mark.django_db
def test_finished_fight_survives_proposal_going_to_draft(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(is_draft=True)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert any(m.level == message_levels.WARNING for m in resp.context["messages"])
    assert resp.context["can_see_solution"]


@pytest.mark.django_db
def test_draft_still_denied_to_someone_who_never_started(otis):
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create(is_draft=True)
    otis.login(user)
    otis.get_denied("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_active_fight_survives_switch_to_casual_mode(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    # Going casual is normally blocked mid-fight; force it to model any way it slips
    # through (a stale tab, an admin edit) and check the session is still usable.
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    otis.get_20x("oime-proposal-fight", proposal.pk)
    otis.assert_30x(otis.post("oime-submit-answer", proposal.pk, data={"answer": 42}))
    assert (
        OIMEFight.objects.get(contributor=contributor, proposal=proposal).status
        == "OIME_OK"
    )
