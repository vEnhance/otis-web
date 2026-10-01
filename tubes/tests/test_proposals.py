import pytest
from django.contrib.auth.models import Group

from core.factories import UserFactory
from tubes.factories import (
    OIMECommentFactory,
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
)
from tubes.models import OIMEComment, OIMEFight, OIMEProposal

from .helpers import verified_contributor, verified_staff

# ---------------------------------------------------------------------------
# Proposal creation / editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_proposal(otis):
    user, contributor = verified_contributor()
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

    proposal = OIMEProposal.objects.get()
    assert proposal.author == contributor
    assert proposal.answer == 2
    assert proposal.archived is False


@pytest.mark.django_db
def test_credit_defaults_to_author_name(otis):

    contributor = OIMEContributorFactory.create(display_name="Ada Lovelace")
    proposal = OIMEProposalFactory.create(author=contributor, credit="")
    # No explicit credit → falls back to the author's display name.
    assert proposal.credit_display == "Ada Lovelace"
    proposal.credit = "Ada Lovelace and a friend"
    assert proposal.credit_display == "Ada Lovelace and a friend"


@pytest.mark.django_db
def test_create_proposal_prefills_credit(otis):
    user, contributor = verified_contributor()
    contributor.display_name = "Grace H."
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-create")
    assert resp.context["form"].initial["credit"] == "Grace H."


@pytest.mark.django_db
def test_credit_saved_on_create(otis):
    user, _ = verified_contributor()
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

    proposal = OIMEProposal.objects.get()
    assert proposal.credit == "Alice & Bob"
    assert proposal.credit_display == "Alice & Bob"


@pytest.mark.django_db
def test_hidden_contributor_uses_anonymous_alias(otis):

    contributor = OIMEContributorFactory.create(
        display_name="Real Name", hide_from_leaderboards=True
    )
    assert contributor.leaderboard_name.startswith("Anonymous ")
    assert "Real Name" not in contributor.leaderboard_name
    contributor.hide_from_leaderboards = False
    assert contributor.leaderboard_name == "Real Name"


@pytest.mark.django_db
def test_leaderboard_hides_name_when_requested(otis):

    user, viewer = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, _ = verified_contributor()
    _, other_contributor = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other_contributor)
    otis.login(user)
    otis.get_40x("oime-proposal-update", proposal.pk)


@pytest.mark.django_db
def test_staff_can_update_any_proposal(otis):
    _, contributor = verified_contributor()
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
def test_proposal_list_marks_upvoted_rows(otis):
    user, contributor = verified_contributor()
    hearted = OIMEProposalFactory.create()
    OIMEProposalFactory.create()
    # Another contributor's upvote must not bold the row for this user.
    OIMEProposalFactory.create().upvotes.add(OIMEContributorFactory.create())
    hearted.upvotes.add(contributor)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert {p.pk for p in resp.context["proposals"] if p.has_upvoted} == {hearted.pk}
    otis.assert_testid(resp, "table-upvoted", count=1)


@pytest.mark.django_db
def test_archived_hidden_from_regular_users(otis):
    user, _ = verified_contributor()
    other_proposal = OIMEProposalFactory.create(archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert other_proposal not in resp.context["proposals"]


@pytest.mark.django_db
def test_archived_hidden_from_own_author(otis):
    user, contributor = verified_contributor()
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
    _, contributor = verified_contributor()
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
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=False)
    otis.login(user)
    resp = otis.post("oime-proposal-archive", proposal.pk)
    assert resp.status_code == 403
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_author_cannot_toggle_own_proposal_archive(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=False)
    otis.login(user)
    resp = otis.post("oime-proposal-archive", proposal.pk)
    assert resp.status_code == 403
    proposal.refresh_from_db()
    assert proposal.archived is False


@pytest.mark.django_db
def test_archived_author_sees_note_but_no_archive_button(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "proposal-archived-note")
    # only a superuser gets the archive toggle
    otis.assert_no_testid(resp, "proposal-archive-toggle")


@pytest.mark.django_db
def test_archived_not_readable_by_other_users(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    otis.login(user)
    otis.get_40x("oime-proposal-detail", proposal.pk)
    otis.get_40x("oime-start-fight", proposal.pk)
    otis.get_40x("oime-proposal-fight", proposal.pk)
    otis.get_40x("oime-proposal-results", proposal.pk)
    otis.post_40x("oime-reveal", proposal.pk)


@pytest.mark.django_db
def test_archived_readable_by_its_author(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_see_solution"]


@pytest.mark.django_db
def test_archived_readable_by_staff(otis):
    staff, _ = verified_staff()
    proposal = OIMEProposalFactory.create(archived=True)
    otis.login(staff)
    otis.get_20x("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_archived_cannot_start_timed_session(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    otis.login(user)
    resp = otis.post("oime-start-fight", proposal.pk)
    assert resp.status_code == 403
    assert not OIMEFight.objects.exists()


@pytest.mark.django_db
def test_archived_cannot_start_timed_session_even_as_staff(otis):
    # Staff keep read access, but the problem is out of circulation for them too.
    staff, _ = verified_staff()
    proposal = OIMEProposalFactory.create(archived=True)
    otis.login(staff)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert not resp.context["can_start_fight"]
    resp = otis.post("oime-start-fight", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEFight.objects.exists()


@pytest.mark.django_db
def test_archived_cannot_be_upvoted(otis):
    user, contributor = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    # A finished session keeps this contributor's read access to the problem.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert not resp.context["can_upvote"]
    resp = otis.post("oime-upvote", proposal.pk)
    assert resp.status_code == 403
    assert proposal.upvotes.count() == 0


@pytest.mark.django_db
def test_archived_cannot_be_upvoted_by_its_author(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert not resp.context["can_upvote"]
    resp = otis.post("oime-upvote", proposal.pk)
    assert resp.status_code == 403
    assert proposal.upvotes.count() == 0


@pytest.mark.django_db
def test_archived_cannot_be_commented_on(otis):
    user, contributor = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_no_testid(resp, "comment-form")
    resp = otis.post(
        "oime-proposal-detail",
        proposal.pk,
        data={"submit_comment": "1", "content": "Nice problem!"},
    )
    assert resp.status_code == 403
    assert not OIMEComment.objects.exists()


@pytest.mark.django_db
def test_archived_comment_cannot_be_edited(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, archived=True)
    comment = OIMECommentFactory.create(
        author=contributor, proposal=proposal, content="Original"
    )
    otis.login(user)
    resp = otis.post("oime-comment-edit", comment.pk, data={"content": "Edited"})
    assert resp.status_code == 403
    comment.refresh_from_db()
    assert comment.content == "Original"


@pytest.mark.django_db
def test_archived_keeps_access_for_unfinished_session(otis):
    # Archiving mid-session must not strand an attempt with its clock still running.
    user, contributor = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    otis.get_20x("oime-proposal-fight", proposal.pk)
    resp = otis.post("oime-give-up", proposal.pk)
    otis.assert_30x(resp)
    fight = OIMEFight.objects.get(contributor=contributor, proposal=proposal)
    assert fight.status == "OIME_FAIL"


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_draft_hidden_from_regular_users(otis):
    user, _ = verified_contributor()
    other_proposal = OIMEProposalFactory.create(is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert other_proposal not in resp.context["proposals"]


@pytest.mark.django_db
def test_draft_hidden_from_own_author_on_main_list(otis):
    user, contributor = verified_contributor()
    own_proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert own_proposal not in resp.context["proposals"]
    assert own_proposal not in resp.context["own_proposals"]


@pytest.mark.django_db
def test_draft_not_viewable_by_others(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, is_draft=True)
    otis.login(user)
    otis.get_40x("oime-proposal-detail", proposal.pk)
    otis.get_40x("oime-start-fight", proposal.pk)
    otis.get_40x("oime-proposal-results", proposal.pk)


@pytest.mark.django_db
def test_draft_viewable_by_its_author(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_see_solution"]


@pytest.mark.django_db
def test_create_proposal_as_draft(otis):
    user, _ = verified_contributor()
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

    proposal = OIMEProposal.objects.get()
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_update_can_publish_a_draft(otis):
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
