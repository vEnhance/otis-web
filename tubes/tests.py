import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from core.factories import UserFactory

from .factories import (
    OIMEAttemptFactory,
    OIMECommentFactory,
    OIMEContributorFactory,
    OIMEProposalFactory,
)
from .models import OIMEAttempt, OIMEComment, OIMEContributor


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
    otis.get_20x("oime-proposal-detail", proposal.pk)


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


# ---------------------------------------------------------------------------
# Spoil / unspoiled logic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unspoiled_hides_solution(otis):
    user, _ = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_not_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_spoiled_sees_solution(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.spoil_before = timezone.now()
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_spoil_only_applies_to_old_proposals(otis):
    # proposals created AFTER spoil_before are still unspoiled
    user, contributor = _verified_contributor()
    contributor.spoil_before = timezone.now()
    contributor.save()
    # create proposal after spoil_before is set — it will have a newer created_at
    proposal = OIMEProposalFactory.create()
    # Manually backdate proposal to before spoil_before to verify logic
    from .models import OIMEProposal

    OIMEProposal.objects.filter(pk=proposal.pk).update(
        created_at=contributor.spoil_before  # type: ignore[arg-type]
    )
    proposal.refresh_from_db()
    # proposal.created_at == spoil_before → spoiled (<=)
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_spoil_self_sets_spoil_before(otis):
    user, contributor = _verified_contributor()
    otis.login(user)
    resp = otis.post("oime-spoil")
    otis.assert_30x(resp)
    contributor.refresh_from_db()
    assert contributor.spoil_before is not None


@pytest.mark.django_db
def test_spoiled_can_comment(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.spoil_before = timezone.now()
    contributor.save()
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
    resp = otis.post("oime-start-attempt", proposal.pk)
    otis.assert_30x(resp)
    assert OIMEAttempt.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


@pytest.mark.django_db
def test_correct_answer_solves(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-submit-answer", proposal.pk, data={"answer": 42})
    otis.assert_30x(resp)
    attempt = OIMEAttempt.objects.get(contributor=contributor, proposal=proposal)
    assert attempt.status == "OIME_OK"
    assert attempt.solve_time_seconds is not None


@pytest.mark.django_db
def test_wrong_answer_increments_count(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    otis.post("oime-submit-answer", proposal.pk, data={"answer": 99})
    attempt = OIMEAttempt.objects.get(contributor=contributor, proposal=proposal)
    assert attempt.status == "OIME_TBD"
    assert attempt.wrong_answers == 1


@pytest.mark.django_db
def test_give_up(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEAttemptFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.post("oime-give-up", proposal.pk)
    otis.assert_30x(resp)
    attempt = OIMEAttempt.objects.get(contributor=contributor, proposal=proposal)
    assert attempt.status == "OIME_FAIL"
    assert attempt.submitted_at is not None


@pytest.mark.django_db
def test_gave_up_sees_solution(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_cannot_comment_before_spoiled(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEAttemptFactory.create(
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
def test_spoiled_cannot_start_attempt(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.spoil_before = timezone.now()
    contributor.save()
    otis.login(user)
    resp = otis.post("oime-start-attempt", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEAttempt.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


@pytest.mark.django_db
def test_author_cannot_start_attempt(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.post("oime-start-attempt", proposal.pk)
    otis.assert_30x(resp)
    assert not OIMEAttempt.objects.filter(
        contributor=contributor, proposal=proposal
    ).exists()


# ---------------------------------------------------------------------------
# Upvotes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upvote_after_solving(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEAttemptFactory.create(
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
    contributor.spoil_before = timezone.now()
    contributor.save()
    proposal.upvotes.add(contributor)
    otis.login(user)
    otis.post("oime-upvote", proposal.pk)
    assert not proposal.upvotes.filter(pk=contributor.pk).exists()


@pytest.mark.django_db
def test_author_cannot_upvote_own_proposal(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    otis.login(user)
    resp = otis.post("oime-upvote", proposal.pk)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Comment editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_author_can_edit_own_comment(otis):
    user, contributor = _verified_contributor()
    proposal = OIMEProposalFactory.create()
    contributor.spoil_before = timezone.now()
    contributor.save()
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
