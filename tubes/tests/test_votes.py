from datetime import timedelta

import pytest
from django.utils import timezone

from tubes.factories import (
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
)
from tubes.models import OIMEFight

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Upvotes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upvote_after_solving(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.post("oime-upvote", proposal.pk)
    otis.assert_30x(resp)
    assert proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_upvote_toggles_off(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    proposal.upvotes.add(contributor)
    otis.login(user)
    otis.post("oime-upvote", proposal.pk)
    assert not proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_upvote_from_subject_browse_returns_to_the_same_page(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create(subject="A", difficulty=3)
    otis.login(user)
    resp = otis.post(
        "oime-upvote",
        proposal.pk,
        data={
            "back_subject": "A",
            "back_params": "sort=votes&difficulty=3&page=2",
        },
    )
    otis.assert_30x(resp)
    assert resp.url == "/tubes/browse/A/?sort=votes&difficulty=3&page=2"
    assert proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data",
    [
        # No return target at all: an ordinary vote from the problem's own page.
        {},
        # A forged target cannot send the voter anywhere but this browser.
        {"back_subject": "https://evil.example.com"},
        {"back_subject": "Z"},
    ],
)
def test_upvote_falls_back_to_the_detail_page(otis, data: dict[str, str]):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-upvote", proposal.pk, data=data)
    otis.assert_30x(resp)
    assert resp.url == f"/tubes/proposal/{proposal.pk}/"
    assert proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_upvote_return_ignores_bogus_browse_params(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create(subject="G")
    otis.login(user)
    resp = otis.post(
        "oime-upvote",
        proposal.pk,
        data={"back_subject": "G", "back_params": "difficulty=9&page=banana&sort=x"},
    )
    otis.assert_30x(resp)
    assert resp.url == "/tubes/browse/G/"


@pytest.mark.django_db
def test_upvote_allowed_during_a_running_fight(otis):
    # Voting needs the statement, not the solution, so a clock still running is no
    # reason to withhold the heart from someone already reading the problem. The
    # casual browser is where this is reachable: the detail view sends a ranked
    # contributor mid-fight to the fight page instead.
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create(subject="C")
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-upvote", proposal.pk, data={"back_subject": "C"})
    otis.assert_30x(resp)
    assert resp.url == "/tubes/browse/C/"
    assert proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_upvote_denied_before_the_statement_is_seen(otis):
    # Ranked mode hides the statement until a fight starts, so there is nothing to
    # form an opinion about yet.
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-start-fight", proposal.pk)
    assert not resp.context["can_upvote"]
    resp = otis.post("oime-upvote", proposal.pk)
    assert resp.status_code == 403
    assert proposal.upvotes.count() == 0


@pytest.mark.django_db
def test_author_can_upvote_own_proposal(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.post("oime-upvote", proposal.pk)
    otis.assert_30x(resp)
    assert proposal.upvotes.filter(pk=contributor.pk).exists()


# ---------------------------------------------------------------------------
# Fight results leaderboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_results_hidden_while_still_fightable(otis):
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # A ranked solver who can still fight may not peek at others' results.
    resp = otis.get("oime-proposal-results", proposal.pk)
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/")


@pytest.mark.django_db
def test_results_visible_to_author(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    otis.get_20x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_detail_explains_solved_status(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    fight = OIMEFightFactory.create(
        contributor=contributor,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=1,
    )
    now = timezone.now()
    OIMEFight.objects.filter(pk=fight.pk).update(
        started_at=now - timedelta(seconds=125),
        submitted_at=now,
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["fight"].is_success
    assert resp.context["fight"].time_display == "02:05"


@pytest.mark.django_db
def test_detail_explains_gave_up_status(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["fight"].status == "OIME_FAIL"


@pytest.mark.django_db
def test_detail_shows_stats_summary(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    # Viewer has fought (so the summary shows), plus three clean solvers whose times
    # {100, 185, 300} give a clear fastest and median.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    for seconds in (100, 185, 300):
        fight = OIMEFightFactory.create(
            contributor=OIMEContributorFactory.create(),
            proposal=proposal,
            status="OIME_OK",
            wrong_answers=0,
        )
        now = timezone.now()
        OIMEFight.objects.filter(pk=fight.pk).update(
            started_at=now - timedelta(seconds=seconds),
            submitted_at=now,
        )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    stats = resp.context["stats"]
    assert stats["total"] == 4
    assert stats["first_correct"] == 3
    assert stats["fastest_clean"].time_display == "01:40"  # 100s
    assert stats["median_clean"] == "03:05"  # median of 100/185/300 → 185s


@pytest.mark.django_db
def test_results_visible_to_casual_browser(otis):
    # Casual browsers can no longer fight, so they may view the leaderboard.
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    otis.get_20x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_results_ranked_for_ineligible_solver(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    # Viewer has finished their own fight, so they are eligible to see results.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    fast = OIMEContributorFactory.create()
    slow = OIMEContributorFactory.create()
    now = timezone.now()
    slow_fight = OIMEFightFactory.create(
        contributor=slow, proposal=proposal, status="OIME_OK", wrong_answers=0
    )
    OIMEFight.objects.filter(pk=slow_fight.pk).update(
        started_at=now - timedelta(seconds=300), submitted_at=now
    )
    fast_fight = OIMEFightFactory.create(
        contributor=fast, proposal=proposal, status="OIME_OK", wrong_answers=0
    )
    OIMEFight.objects.filter(pk=fast_fight.pk).update(
        started_at=now - timedelta(seconds=100), submitted_at=now
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    fights = resp.context["fights"]
    # Solved-and-fastest ranks first; the unsolved give-up ranks last.
    assert fights[0].contributor == fast
    assert fights[1].contributor == slow
    assert fights[-1].contributor == contributor
    # The shared stats summary is computed here too.
    assert resp.context["stats"]["total"] == 3
