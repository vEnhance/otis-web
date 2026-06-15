from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from core.factories import UserFactory

from .factories import (
    OIMECommentFactory,
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
)
from .models import OIMEComment, OIMEContributor, OIMEFight


def _verified_contributor(username: str = "alice") -> tuple[object, object]:
    """Helper: verified-group user + OIMEContributor."""
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(username=username, groups=(verified_group,))
    contributor = OIMEContributorFactory.create(user=user)
    return user, contributor


# ---------------------------------------------------------------------------
# Verified-gating: no contributor → redirect to setup
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unverified_cannot_access_proposal_list(otis):
    # Unverified → no contributor → redirected to setup → setup enforces @verified_required
    UserFactory.create(username="mallory")
    otis.login("mallory")
    resp = otis.get("oime-proposal-list")
    otis.assert_30x(resp)
    assert resp.url.endswith("/tubes/setup/")
    otis.get_40x("oime-setup")


@pytest.mark.django_db
def test_unverified_cannot_view_proposal_detail(otis):
    proposal = OIMEProposalFactory.create()
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_no_contributor_redirects_to_setup(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.get("oime-proposal-list")
    otis.assert_30x(resp)
    assert resp.url.endswith("/tubes/setup/")


@pytest.mark.django_db
def test_verified_can_access_setup(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    otis.get_20x("oime-setup")


@pytest.mark.django_db
def test_verified_with_contributor_can_list(otis):
    user, _ = _verified_contributor()
    otis.login(user)
    otis.get_20x("oime-proposal-list")


@pytest.mark.django_db
def test_verified_with_contributor_can_view_proposal(otis):
    user, _ = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # A fresh ranked solver is routed from detail to the pre-fight start screen.
    resp = otis.get("oime-proposal-detail", proposal.pk)
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/begin/")
    otis.get_20x("oime-start-fight", proposal.pk)


# ---------------------------------------------------------------------------
# Setup / onboarding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_creates_contributor(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.post("oime-setup", data={"display_name": "Alice A."})
    otis.assert_30x(resp)
    assert OIMEContributor.objects.filter(user=user, display_name="Alice A.").exists()


@pytest.mark.django_db
def test_setup_can_edit_display_name(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    otis.post("oime-setup", data={"display_name": "New Name"})
    contributor.refresh_from_db()
    assert contributor.display_name == "New Name"


# ---------------------------------------------------------------------------
# Proposal creation / editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_proposal(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    resp = otis.post(
        "oime-proposal-create",
        data={
            "title": "Squares",
            "statement": "Find all $x$ such that $x^2 = 4$.",
            "answer": 2,
            "solution": "Clearly $x = \\pm 2$.",
            "subject": "A",
            "difficulty": 1,
        },
    )
    otis.assert_30x(resp)
    from .models import OIMEProposal

    proposal = OIMEProposal.objects.get()
    assert proposal.author == contributor
    assert proposal.answer == 2
    assert proposal.archived is False


@pytest.mark.django_db
def test_credit_defaults_to_author_name(otis):
    from .factories import OIMEContributorFactory

    contributor = OIMEContributorFactory.create(display_name="Ada Lovelace")
    proposal = OIMEProposalFactory.create(author=contributor, credit="")
    # No explicit credit → falls back to the author's display name.
    assert proposal.credit_display == "Ada Lovelace"
    proposal.credit = "Ada Lovelace and a friend"
    assert proposal.credit_display == "Ada Lovelace and a friend"


@pytest.mark.django_db
def test_create_proposal_prefills_credit(otis):
    user, contributor = _verified_contributor()
    contributor.display_name = "Grace H."
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-create")
    otis.assert_has(resp, "Grace H.")


@pytest.mark.django_db
def test_credit_saved_on_create(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    otis.post(
        "oime-proposal-create",
        data={
            "title": "Squares",
            "credit": "Alice & Bob",
            "statement": "Find $x$.",
            "answer": 2,
            "solution": "Two.",
            "subject": "A",
            "difficulty": 1,
        },
    )
    from .models import OIMEProposal

    proposal = OIMEProposal.objects.get()
    assert proposal.credit == "Alice & Bob"
    assert proposal.credit_display == "Alice & Bob"


@pytest.mark.django_db
def test_hidden_contributor_uses_anonymous_alias(otis):
    from .factories import OIMEContributorFactory

    contributor = OIMEContributorFactory.create(
        display_name="Real Name", hide_from_leaderboards=True
    )
    assert contributor.leaderboard_name.startswith("Anonymous ")
    assert "Real Name" not in contributor.leaderboard_name
    contributor.hide_from_leaderboards = False
    assert contributor.leaderboard_name == "Real Name"


@pytest.mark.django_db
def test_leaderboard_hides_name_when_requested(otis):
    from .factories import OIMEContributorFactory

    user, viewer = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(contributor=viewer, proposal=proposal, status="OIME_FAIL")
    hidden = OIMEContributorFactory.create(
        display_name="Secret Solver", hide_from_leaderboards=True
    )
    OIMEFightFactory.create(
        contributor=hidden,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
        solve_time_seconds=90,
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    otis.assert_not_has(resp, "Secret Solver")
    otis.assert_has(resp, "Anonymous ")


@pytest.mark.django_db
def test_setup_saves_name_visibility_preferences(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    otis.post(
        "oime-setup",
        data={
            "display_name": contributor.display_name,
            "hide_from_leaderboards": "on",
            "hide_from_acknowledgments": "on",
        },
    )
    contributor.refresh_from_db()
    assert contributor.hide_from_leaderboards is True
    assert contributor.hide_from_acknowledgments is True


@pytest.mark.django_db
def test_update_own_proposal(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, answer=5)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
            "title": proposal.title,
            "statement": proposal.statement,
            "answer": 7,
            "solution": proposal.solution,
            "subject": proposal.subject,
            "difficulty": proposal.difficulty,
        },
    )
    otis.assert_30x(resp)
    proposal.refresh_from_db()
    assert proposal.answer == 7


@pytest.mark.django_db
def test_cannot_change_difficulty_after_submission(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, difficulty=2)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
            "title": proposal.title,
            "statement": proposal.statement,
            "answer": proposal.answer,
            "solution": proposal.solution,
            "subject": proposal.subject,
            "difficulty": 5,
        },
    )
    otis.assert_30x(resp)
    proposal.refresh_from_db()
    assert proposal.difficulty == 2


@pytest.mark.django_db
def test_cannot_update_others_proposal(otis):
    user, _ = _verified_contributor()
    _, other_contributor = _verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other_contributor)
    otis.login(user)
    otis.get_40x("oime-proposal-update", proposal.pk)


@pytest.mark.django_db
def test_staff_can_update_any_proposal(otis):
    _, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, answer=3)
    UserFactory.create(username="staff", is_staff=True)
    otis.login("staff")
    resp = otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
            "title": proposal.title,
            "statement": proposal.statement,
            "answer": 9,
            "solution": proposal.solution,
            "subject": proposal.subject,
            "difficulty": proposal.difficulty,
        },
    )
    otis.assert_30x(resp)
    proposal.refresh_from_db()
    assert proposal.answer == 9


# ---------------------------------------------------------------------------
# Archived proposals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_archived_hidden_from_regular_users(otis):
    user, contributor = _verified_contributor()
    other_proposal = OIMEProposalFactory.create(archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    otis.assert_not_has(resp, other_proposal.statement[:20])


@pytest.mark.django_db
def test_archived_visible_to_own_author(otis):
    user, contributor = _verified_contributor()
    OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    otis.assert_has(resp, "archived")


@pytest.mark.django_db
def test_staff_can_toggle_archive(otis):
    _, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=False)
    UserFactory.create(username="staff", is_staff=True)
    otis.login("staff")
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is True
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_non_staff_cannot_toggle_archive(otis):
    user, _ = _verified_contributor()
    _, other = _verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=False)
    otis.login(user)
    resp = otis.post("oime-proposal-archive", proposal.pk)
    assert resp.status_code == 403
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_author_can_toggle_own_proposal_archive(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=False)
    otis.login(user)
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is True
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is False


# ---------------------------------------------------------------------------
# Casual mode / solution reveal logic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ranked_hides_solution(otis):
    user, _ = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # Pre-fight, a ranked solver sees only the start screen, never the solution.
    resp = otis.get_20x("oime-start-fight", proposal.pk)
    otis.assert_has(resp, "Start solving")
    otis.assert_not_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_start_screen_redirects_when_cannot_fight(otis):
    # Someone who already finished a fight can't use the start screen → back to detail.
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
        solve_time_seconds=60,
    )
    otis.login(user)
    resp = otis.get("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/")


@pytest.mark.django_db
def test_casual_hides_solution_until_revealed(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    # Casual: statement visible, solution still hidden behind the reveal action,
    # but a client-side self-checker is offered.
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_not_has(resp, "oime-answer-section")
    otis.assert_has(resp, "Reveal solution")
    otis.assert_has(resp, "oime-self-check")


@pytest.mark.django_db
def test_casual_reveal_shows_solution(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.post("oime-reveal", proposal.pk)
    otis.assert_30x(resp)
    assert contributor.revealed_proposals.filter(pk=proposal.pk).exists()
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_ranked_escape_hatch_reveal(otis):
    # A ranked solver who already knows a problem can reveal it without a fight,
    # which forfeits the chance to fight it for a recorded time.
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-reveal", proposal.pk)
    otis.assert_30x(resp)
    assert contributor.revealed_proposals.filter(pk=proposal.pk).exists()
    # The solution is now visible and the start-fight option is gone.
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


@pytest.mark.django_db
def test_cannot_reveal_during_active_fight(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-reveal", proposal.pk)
    assert resp.status_code == 403
    assert not contributor.revealed_proposals.exists()


@pytest.mark.django_db
def test_go_casual_sets_casual_mode(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    resp = otis.post("oime-casual")
    otis.assert_30x(resp)
    contributor.refresh_from_db()
    assert contributor.casual_mode is True


@pytest.mark.django_db
def test_casual_completed_fight_shows_as_solved(otis):
    # A casual solver who completed a fight earlier should see the recorded result
    # ("MM:SS (✖N)"), not "Try it" (regression for a list/detail mismatch).
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
        solve_time_seconds=120,
    )
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    otis.assert_has(resp, "02:00")
    otis.assert_not_has(resp, "✖0")
    otis.assert_not_has(resp, "Try it")


@pytest.mark.django_db
def test_go_serious_sets_cutoff_and_locks_old_problems(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    old_proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-serious")
    otis.assert_30x(resp)
    contributor.refresh_from_db()
    assert contributor.casual_mode is False
    assert contributor.ranked_cutoff is not None
    # The pre-existing problem is no longer fightable, but stays browsable casually.
    resp = otis.post("oime-start-fight", old_proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=old_proposal
    ).exists()
    resp = otis.get_20x("oime-proposal-detail", old_proposal.pk)
    otis.assert_has(resp, "Reveal solution")


@pytest.mark.django_db
def test_serious_can_fight_problem_after_cutoff(otis):
    user, contributor = _verified_contributor()
    contributor.ranked_cutoff = timezone.now()
    contributor.save()
    # Created after the cutoff → eligible for a timed fight.
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert OIMEFight.objects.filter(contributor=contributor, proposal=proposal).exists()


@pytest.mark.django_db
def test_casual_revealed_can_comment(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    contributor.revealed_proposals.add(proposal)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-detail",
        proposal.pk,
        data={"submit_comment": "1", "content": "Nice problem!"},
    )
    otis.assert_30x(resp)
    assert OIMEComment.objects.filter(
        proposal=proposal, content="Nice problem!"
    ).exists()


# ---------------------------------------------------------------------------
# Timed solve flow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unspoiled_start_creates_attempt(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert OIMEFight.objects.filter(contributor=contributor, proposal=proposal).exists()


@pytest.mark.django_db
def test_cannot_start_second_concurrent_fight(otis):
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-submit-answer", proposal.pk, data={"answer": 42})
    otis.assert_30x(resp)
    fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
    assert fight.status == "OIME_OK"
    assert fight.solve_time_seconds is not None


@pytest.mark.django_db
def test_wrong_answer_increments_count(otis):
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
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
    from .views import GIVE_UP_RATE_LIMIT, GIVE_UP_WINDOW_MINUTES

    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_cannot_comment_during_active_fight(otis):
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


# ---------------------------------------------------------------------------
# Upvotes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upvote_after_solving(otis):
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    proposal.upvotes.add(contributor)
    otis.login(user)
    otis.post("oime-upvote", proposal.pk)
    assert not proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_author_can_upvote_own_proposal(otis):
    user, contributor = _verified_contributor()
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
    user, _ = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # A ranked solver who can still fight may not peek at others' results.
    resp = otis.get("oime-proposal-results", proposal.pk)
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/")


@pytest.mark.django_db
def test_results_visible_to_author(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    otis.get_20x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_detail_explains_solved_status(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=1,
        solve_time_seconds=125,
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "You solved this problem in 02:05")


@pytest.mark.django_db
def test_detail_explains_gave_up_status(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "You gave up on this problem")


@pytest.mark.django_db
def test_detail_shows_stats_summary(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    # Viewer has fought (so the summary shows), plus three clean solvers whose times
    # {100, 185, 300} give a clear fastest and median.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    for seconds in (100, 185, 300):
        OIMEFightFactory.create(
            contributor=OIMEContributorFactory.create(),
            proposal=proposal,
            status="OIME_OK",
            wrong_answers=0,
            solve_time_seconds=seconds,
        )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "Total testsolvers")
    otis.assert_has(resp, "01:40")  # 100s fastest clean solve
    otis.assert_has(resp, "Median clean solve")
    otis.assert_has(resp, "03:05")  # median of 100/185/300 → 185s


@pytest.mark.django_db
def test_results_visible_to_casual_browser(otis):
    # Casual browsers can no longer fight, so they may view the leaderboard.
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    otis.get_20x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_results_ranked_for_ineligible_solver(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    # Viewer has finished their own fight, so they are eligible to see results.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    fast = OIMEContributorFactory.create()
    slow = OIMEContributorFactory.create()
    OIMEFightFactory.create(
        contributor=slow,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
        solve_time_seconds=300,
    )
    OIMEFightFactory.create(
        contributor=fast,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
        solve_time_seconds=100,
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    fights = resp.context["fights"]
    # Solved-and-fastest ranks first; the unsolved give-up ranks last.
    assert fights[0].contributor == fast
    assert fights[1].contributor == slow
    assert fights[-1].contributor == contributor
    # The shared stats summary is shown here too.
    otis.assert_has(resp, "Total testsolvers")


# ---------------------------------------------------------------------------
# Comment editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_author_can_edit_own_comment(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.casual_mode = True
    contributor.save()
    contributor.revealed_proposals.add(proposal)
    comment = OIMECommentFactory.create(
        author=contributor, proposal=proposal, content="Original"
    )
    otis.login(user)
    resp = otis.post("oime-comment-edit", comment.pk, data={"content": "Edited"})
    otis.assert_30x(resp)
    comment.refresh_from_db()
    assert comment.content == "Edited"


@pytest.mark.django_db
def test_other_contributor_cannot_edit_comment(otis):
    user, _ = _verified_contributor()
    _, other = _verified_contributor("bob")
    proposal = OIMEProposalFactory.create()
    comment = OIMECommentFactory.create(author=other, proposal=proposal)
    otis.login(user)
    resp = otis.post("oime-comment-edit", comment.pk, data={"content": "Hacked"})
    assert resp.status_code == 403
    comment.refresh_from_db()
    assert comment.content != "Hacked"


# ---------------------------------------------------------------------------
# Comment is_edited property
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_comment_is_edited_false_when_fresh(otis):
    comment = OIMECommentFactory.create()
    assert comment.is_edited is False


@pytest.mark.django_db
def test_comment_is_edited_true_after_meaningful_edit(otis):
    comment = OIMECommentFactory.create()
    # Bypass auto_now to simulate an edit made well after creation.
    OIMEComment.objects.filter(pk=comment.pk).update(
        updated_at=comment.created_at + timedelta(minutes=5)
    )
    comment.refresh_from_db()
    assert comment.is_edited is True


@pytest.mark.django_db
def test_comment_is_edited_false_within_threshold(otis):
    comment = OIMECommentFactory.create()
    OIMEComment.objects.filter(pk=comment.pk).update(
        updated_at=comment.created_at + timedelta(seconds=30)
    )
    comment.refresh_from_db()
    assert comment.is_edited is False


@pytest.mark.django_db
def test_edited_label_not_shown_for_fresh_comment(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    OIMECommentFactory.create(author=contributor, proposal=proposal, content="Hi")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_not_has(resp, "edited")


@pytest.mark.django_db
def test_edited_label_shown_after_meaningful_edit(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    comment = OIMECommentFactory.create(
        author=contributor, proposal=proposal, content="Hi"
    )
    OIMEComment.objects.filter(pk=comment.pk).update(
        updated_at=comment.created_at + timedelta(minutes=5)
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "edited")
