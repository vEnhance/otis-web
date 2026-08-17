from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import constants as message_levels
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
    assert resp.context["form"].initial["credit"] == "Grace H."


@pytest.mark.django_db
def test_credit_saved_on_create(otis):
    user, _ = _verified_contributor()
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
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-results", proposal.pk)
    otis.assert_not_has(resp, "Secret Solver")
    assert hidden.leaderboard_name.startswith("Anonymous ")
    assert {f.contributor.leaderboard_name for f in resp.context["fights"]} == {
        viewer.leaderboard_name,
        hidden.leaderboard_name,
    }


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
    user, _ = _verified_contributor()
    other_proposal = OIMEProposalFactory.create(archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert other_proposal not in resp.context["proposals"]


@pytest.mark.django_db
def test_archived_hidden_from_own_author(otis):
    user, contributor = _verified_contributor()
    own_proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert own_proposal not in resp.context["proposals"]
    assert own_proposal not in resp.context["own_proposals"]


@pytest.mark.django_db
def test_archived_hidden_from_staff(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    staff = UserFactory.create(
        username="staff", is_staff=True, groups=(verified_group,)
    )
    OIMEContributorFactory.create(user=staff)
    other_proposal = OIMEProposalFactory.create(archived=True)
    otis.login(staff)
    resp = otis.get_20x("oime-proposal-list")
    assert other_proposal not in resp.context["proposals"]


@pytest.mark.django_db
def test_superuser_can_toggle_archive(otis):
    _, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=False)
    UserFactory.create(username="staff", is_staff=True, is_superuser=True)
    otis.login("staff")
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is True
    otis.post("oime-proposal-archive", proposal.pk)
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_non_superuser_cannot_toggle_archive(otis):
    user, _ = _verified_contributor()
    _, other = _verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=False)
    otis.login(user)
    resp = otis.post("oime-proposal-archive", proposal.pk)
    assert resp.status_code == 403
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_author_cannot_toggle_own_proposal_archive(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=False)
    otis.login(user)
    resp = otis.post("oime-proposal-archive", proposal.pk)
    assert resp.status_code == 403
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_archived_author_sees_note_but_no_archive_button(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "proposal-archived-note")
    # only a superuser gets the archive toggle
    otis.assert_no_testid(resp, "proposal-archive-toggle")


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_draft_hidden_from_regular_users(otis):
    user, _ = _verified_contributor()
    other_proposal = OIMEProposalFactory.create(is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert other_proposal not in resp.context["proposals"]


@pytest.mark.django_db
def test_draft_hidden_from_own_author_on_main_list(otis):
    user, contributor = _verified_contributor()
    own_proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert own_proposal not in resp.context["proposals"]
    assert own_proposal not in resp.context["own_proposals"]


@pytest.mark.django_db
def test_draft_list_shows_own_drafts_only(otis):
    user, contributor = _verified_contributor()
    _, other = _verified_contributor("bob")
    mine = OIMEProposalFactory.create(
        author=contributor, is_draft=True, title="My draft"
    )
    OIMEProposalFactory.create(author=contributor, is_draft=False, title="My problem")
    OIMEProposalFactory.create(author=other, is_draft=True, title="Bob's draft")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-drafts")
    assert list(resp.context["proposals"]) == [mine]


@pytest.mark.django_db
def test_draft_list_hides_archived_drafts(otis):
    user, contributor = _verified_contributor()
    OIMEProposalFactory.create(
        author=contributor, is_draft=True, archived=True, title="Archived draft"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-drafts")
    assert list(resp.context["proposals"]) == []


@pytest.mark.django_db
def test_main_list_links_to_drafts(otis):
    user, _ = _verified_contributor()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    otis.assert_has(resp, otis.url("oime-proposal-drafts"))


@pytest.mark.django_db
def test_draft_not_viewable_by_others(otis):
    user, _ = _verified_contributor()
    _, other = _verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, is_draft=True)
    otis.login(user)
    otis.get_40x("oime-proposal-detail", proposal.pk)
    otis.get_40x("oime-start-fight", proposal.pk)
    otis.get_40x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_draft_viewable_by_its_author(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_see_solution"]


@pytest.mark.django_db
def test_create_proposal_as_draft(otis):
    user, _ = _verified_contributor()
    otis.login(user)
    otis.post(
        "oime-proposal-create",
        data={
            "title": "Draft Squares",
            "statement": "Find all $x$ such that $x^2 = 4$.",
            "answer": 2,
            "solution": "Clearly $x = \\pm 2$.",
            "subject": "A",
            "difficulty": 1,
            "is_draft": "on",
        },
    )
    from .models import OIMEProposal

    proposal = OIMEProposal.objects.get()
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_update_can_publish_a_draft(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    # Omitting the checkbox unchecks it, publishing the problem.
    otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
            "title": proposal.title,
            "statement": proposal.statement,
            "answer": proposal.answer,
            "solution": proposal.solution,
            "subject": proposal.subject,
        },
    )
    proposal.refresh_from_db()
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_update_can_return_a_proposal_to_draft(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=False)
    otis.login(user)
    otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
            "title": proposal.title,
            "statement": proposal.statement,
            "answer": proposal.answer,
            "solution": proposal.solution,
            "subject": proposal.subject,
            "is_draft": "on",
        },
    )
    proposal.refresh_from_db()
    assert proposal.is_draft is True


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
    assert resp.context["can_start_fight"]
    assert not resp.context["can_see_solution"]


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
    assert resp.context["casual"]
    # the reveal button and the client-side checker are both gated on this flag
    assert not resp.context["can_see_solution"]


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
    assert resp.context["can_see_solution"]


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
    assert resp.context["can_see_solution"]
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
    fight = OIMEFightFactory.create(
        contributor=contributor,
        proposal=proposal,
        status="OIME_OK",
        wrong_answers=0,
    )
    now = timezone.now()
    OIMEFight.objects.filter(pk=fight.pk).update(
        started_at=now - timedelta(seconds=120),
        submitted_at=now,
    )
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    (row,) = resp.context["completed_proposals"]
    assert row.user_list_status == "completed"
    assert row.user_fight.time_display == "02:00"
    # a clean solve renders no wrong-answer marker
    assert row.user_fight.wrong_answers == 0


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
    assert not resp.context["can_see_solution"]


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
# Casual full-statement browser
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_casual_browse_shows_statements_of_one_subject(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    wanted = OIMEProposalFactory.create(subject="G", statement="Geometry statement.")
    other_subject = OIMEProposalFactory.create(subject="N", statement="Number theory.")
    otis.login(user)
    resp = otis.get_20x("oime-casual-browse", "G")
    assert list(resp.context["page_obj"]) == [wanted]
    assert other_subject not in resp.context["page_obj"]
    # this browser exists to put whole statements on the page, so that is content
    otis.assert_has(resp, "Geometry statement.")
    otis.assert_not_has(resp, "Number theory.")


@pytest.mark.django_db
def test_casual_browse_never_shows_answers_or_solutions(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="A", answer=123, solution="Secret solution.")
    otis.login(user)
    # bulk browse has no per-proposal solver context; the page must simply never
    # carry a solution, so this stays a leakage check on the bytes
    resp = otis.get_20x("oime-casual-browse", "A")
    otis.assert_not_has(resp, "Secret solution.")


@pytest.mark.django_db
def test_casual_browse_includes_spoiled_problems_but_marks_them(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    fresh = OIMEProposalFactory.create(subject="C", statement="Brand new one.")
    own = OIMEProposalFactory.create(
        author=contributor, subject="C", statement="I wrote this."
    )
    revealed = OIMEProposalFactory.create(subject="C", statement="Already revealed.")
    contributor.revealed_proposals.add(revealed)
    solved = OIMEProposalFactory.create(subject="C", statement="Already solved.")
    OIMEFightFactory.create(contributor=contributor, proposal=solved, status="OIME_OK")
    gave_up = OIMEProposalFactory.create(subject="C", statement="Already gave up.")
    OIMEFightFactory.create(
        contributor=contributor, proposal=gave_up, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-casual-browse", "C")
    # Every problem is listed, but each is labelled by how the viewer has
    # already engaged with it.
    statuses = {p.pk: p.browse_status for p in resp.context["page_obj"]}
    assert statuses == {
        fresh.pk: "new",
        own.pk: "author",
        revealed.pk: "revealed",
        solved.pk: "solved",
        gave_up.pk: "attempted",
    }
    spoiled = {p.pk for p in resp.context["page_obj"] if p.spoiled}
    assert spoiled == {own.pk, revealed.pk, solved.pk, gave_up.pk}


@pytest.mark.django_db
def test_casual_browse_hides_archived_and_drafts(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="N", archived=True, statement="Archived one.")
    OIMEProposalFactory.create(subject="N", is_draft=True, statement="Draft one.")
    # Even the viewer's own draft stays out; drafts live on the drafts page only.
    OIMEProposalFactory.create(
        author=contributor, subject="N", is_draft=True, statement="My draft."
    )
    otis.login(user)
    resp = otis.get_20x("oime-casual-browse", "N")
    assert list(resp.context["page_obj"]) == []


@pytest.mark.django_db
def test_casual_browse_orders_newest_first(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    oldest = OIMEProposalFactory.create(subject="A")
    middle = OIMEProposalFactory.create(subject="A")
    newest = OIMEProposalFactory.create(subject="A")
    otis.login(user)
    resp = otis.get_20x("oime-casual-browse", "A")
    assert list(resp.context["page_obj"]) == [newest, middle, oldest]


@pytest.mark.django_db
def test_casual_browse_paginates(otis):
    from .views import CASUAL_BROWSE_PAGE_SIZE

    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposals = [
        OIMEProposalFactory.create(subject="G")
        for _ in range(CASUAL_BROWSE_PAGE_SIZE + 3)
    ]
    otis.login(user)
    resp = otis.get_20x("oime-casual-browse", "G")
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.num_pages == 2
    assert len(page_obj.object_list) == CASUAL_BROWSE_PAGE_SIZE
    assert list(page_obj) == list(reversed(proposals))[:CASUAL_BROWSE_PAGE_SIZE]
    resp = otis.get_20x("oime-casual-browse", "G", data={"page": 2})
    page_obj = resp.context["page_obj"]
    assert list(page_obj) == list(reversed(proposals))[CASUAL_BROWSE_PAGE_SIZE:]
    # Statuses are still computed on later pages.
    assert all(p.browse_status == "new" for p in page_obj)


@pytest.mark.django_db
def test_casual_browse_bad_page_falls_back_to_first(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="G")
    otis.login(user)
    for bad_page in ("0", "99", "banana"):
        resp = otis.get_20x("oime-casual-browse", "G", data={"page": bad_page})
        assert resp.context["page_obj"].number == 1


@pytest.mark.django_db
def test_casual_browse_refused_in_ranked_mode(otis):
    # Ranked statements are meant to be read for the first time under the clock.
    user, _ = _verified_contributor()
    OIMEProposalFactory.create(subject="G", statement="Geometry statement.")
    otis.login(user)
    resp = otis.get("oime-casual-browse", "G")
    otis.assert_30x(resp)
    assert resp.url.endswith("/tubes/proposals/")


@pytest.mark.django_db
def test_casual_browse_rejects_unknown_subject(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    otis.get_not_found("oime-casual-browse", "Z")


@pytest.mark.django_db
def test_casual_browse_requires_verification(otis):
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-casual-browse", "G")


@pytest.mark.django_db
def test_casual_list_links_to_browser(otis):
    user, contributor = _verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert resp.context["casual"]
    otis.assert_has(resp, otis.url("oime-casual-browse", "G"))


@pytest.mark.django_db
def test_ranked_list_does_not_link_to_browser(otis):
    user, _ = _verified_contributor()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert not resp.context["casual"]
    otis.assert_not_has(resp, otis.url("oime-casual-browse", "G"))


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
    assert fight.submitted_at is not None


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
    assert resp.context["can_see_solution"]


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
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["fight"].status == "OIME_FAIL"


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
    otis.assert_no_testid(resp, "comment-edited")


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
    otis.assert_testid(resp, "comment-edited")


# ---------------------------------------------------------------------------
# Ending a timed session: caching, and the give-up/time-out boundary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fight_page_is_not_cacheable(otis):
    # Otherwise "back" after giving up restores the page with a live countdown,
    # which reads as though the attempt were still open.
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-fight", proposal.pk)
    assert "no-store" in resp.headers["Cache-Control"]


@pytest.mark.django_db
def test_give_up_after_time_expired_records_tle(otis):
    user, contributor = _verified_contributor()
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
    from .views import GIVE_UP_RATE_LIMIT

    user, contributor = _verified_contributor()
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
def test_detail_shows_gave_up_alert_box(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "fight-gave-up")


# ---------------------------------------------------------------------------
# Landing page: recovering an abandoned timed session
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_landing_links_to_active_fight(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(difficulty=5)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["active_fight"].proposal == proposal


@pytest.mark.django_db
def test_landing_marks_abandoned_fight_as_tle(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(difficulty=1)
    fight = OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    OIMEFight.objects.filter(pk=fight.pk).update(
        started_at=timezone.now() - timedelta(hours=5)
    )
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    fight.refresh_from_db()
    assert fight.status == "OIME_TLE"
    assert fight.submitted_at is not None
    # No point offering to resume a session that has just been closed out.
    assert resp.context["active_fight"] is None


@pytest.mark.django_db
def test_landing_quiet_without_active_fight(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["active_fight"] is None


@pytest.mark.django_db
def test_landing_works_for_anonymous_and_contributorless_users(otis):
    otis.get_20x("oime-landing")
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    otis.get_20x("oime-landing")


# ---------------------------------------------------------------------------
# A started session survives the problem or the mode changing underneath it
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_fight_survives_proposal_going_to_draft(otis):
    user, contributor = _verified_contributor()
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
    user, contributor = _verified_contributor()
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
    user, _ = _verified_contributor()
    proposal = OIMEProposalFactory.create(is_draft=True)
    otis.login(user)
    otis.get_denied("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_active_fight_survives_switch_to_casual_mode(otis):
    user, contributor = _verified_contributor()
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
