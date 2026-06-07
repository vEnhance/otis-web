import pytest

from core.factories import GroupFactory, UserFactory

from .factories import OIMEAttemptFactory, OIMECommentFactory, OIMEProposalFactory, OIMESolverRoleFactory
from .models import OIMEAttempt, OIMEComment, OIMESolverRole


# ---------------------------------------------------------------------------
# Verified-gating
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unverified_cannot_access_proposal_list(otis):
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-proposal-list")


@pytest.mark.django_db
def test_unverified_cannot_create_proposal(otis):
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-proposal-create")


@pytest.mark.django_db
def test_unverified_cannot_view_proposal_detail(otis):
    proposal = OIMEProposalFactory.create()
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_unverified_cannot_access_role_select(otis):
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-role-select")


@pytest.mark.django_db
def test_verified_can_access_proposal_list(otis):
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    otis.get_20x("oime-proposal-list")


@pytest.mark.django_db
def test_verified_can_access_role_select(otis):
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    otis.get_20x("oime-role-select")


@pytest.mark.django_db
def test_verified_can_view_proposal(otis):
    verified_group = GroupFactory(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    proposal = OIMEProposalFactory.create()
    otis.login("alice")
    otis.get_20x("oime-proposal-detail", proposal.pk)


# ---------------------------------------------------------------------------
# Role selection
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_role_select_casual(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.post("oime-role-select", data={"role": "casual"})
    otis.assert_30x(resp)
    assert OIMESolverRole.objects.get(user=alice).is_serious is False


@pytest.mark.django_db
def test_role_select_serious(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.post("oime-role-select", data={"role": "serious"})
    otis.assert_30x(resp)
    assert OIMESolverRole.objects.get(user=alice).is_serious is True


@pytest.mark.django_db
def test_role_can_be_changed(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=False)
    otis.login("alice")
    otis.post("oime-role-select", data={"role": "serious"})
    assert OIMESolverRole.objects.get(user=alice).is_serious is True


# ---------------------------------------------------------------------------
# Proposal creation / editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_proposal(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.post(
        "oime-proposal-create",
        data={
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
    assert proposal.author == alice
    assert proposal.answer == 2


@pytest.mark.django_db
def test_update_own_proposal(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    proposal = OIMEProposalFactory.create(author=alice, answer=5)
    otis.login("alice")
    resp = otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
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
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    bob = UserFactory.create(username="bob", groups=(verified_group,))
    proposal = OIMEProposalFactory.create(author=bob)
    otis.login("alice")
    otis.get_40x("oime-proposal-update", proposal.pk)


@pytest.mark.django_db
def test_staff_can_update_any_proposal(otis):
    verified_group = GroupFactory(name="Verified")
    bob = UserFactory.create(username="bob", groups=(verified_group,))
    proposal = OIMEProposalFactory.create(author=bob, answer=3)
    staff = UserFactory.create(username="staff", is_staff=True)
    otis.login("staff")
    resp = otis.post(
        "oime-proposal-update",
        proposal.pk,
        data={
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
# Casual solver
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_casual_sees_solution(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=False)
    proposal = OIMEProposalFactory.create(answer=42)
    otis.login("alice")
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_casual_can_comment(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=False)
    proposal = OIMEProposalFactory.create()
    otis.login("alice")
    resp = otis.post(
        "oime-proposal-detail",
        proposal.pk,
        data={"submit_comment": "1", "content": "Nice problem!"},
    )
    otis.assert_30x(resp)
    assert OIMEComment.objects.filter(proposal=proposal, content="Nice problem!").exists()


# ---------------------------------------------------------------------------
# Serious solver
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_serious_no_attempt_hides_solution(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create(answer=42)
    otis.login("alice")
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_not_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_serious_start_creates_attempt(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create()
    otis.login("alice")
    resp = otis.post("oime-start-attempt", proposal.pk)
    otis.assert_30x(resp)
    assert OIMEAttempt.objects.filter(user=alice, proposal=proposal).exists()


@pytest.mark.django_db
def test_serious_correct_answer(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(user=alice, proposal=proposal, status="IN_PROGRESS")
    otis.login("alice")
    resp = otis.post("oime-submit-answer", proposal.pk, data={"answer": 42})
    otis.assert_30x(resp)
    attempt = OIMEAttempt.objects.get(user=alice, proposal=proposal)
    assert attempt.status == "CORRECT"
    assert attempt.solve_time_seconds is not None


@pytest.mark.django_db
def test_serious_wrong_answer_increments_count(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(user=alice, proposal=proposal, status="IN_PROGRESS")
    otis.login("alice")
    otis.post("oime-submit-answer", proposal.pk, data={"answer": 99})
    attempt = OIMEAttempt.objects.get(user=alice, proposal=proposal)
    assert attempt.status == "IN_PROGRESS"
    assert attempt.wrong_answers == 1


@pytest.mark.django_db
def test_serious_give_up(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create()
    OIMEAttemptFactory.create(user=alice, proposal=proposal, status="IN_PROGRESS")
    otis.login("alice")
    resp = otis.post("oime-give-up", proposal.pk)
    otis.assert_30x(resp)
    attempt = OIMEAttempt.objects.get(user=alice, proposal=proposal)
    assert attempt.status == "GAVE_UP"
    assert attempt.submitted_at is not None


@pytest.mark.django_db
def test_serious_gave_up_sees_solution(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create(answer=42)
    OIMEAttemptFactory.create(user=alice, proposal=proposal, status="GAVE_UP")
    otis.login("alice")
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, "oime-answer-section")


@pytest.mark.django_db
def test_serious_cannot_comment_before_solving(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    OIMESolverRoleFactory.create(user=alice, is_serious=True)
    proposal = OIMEProposalFactory.create()
    OIMEAttemptFactory.create(user=alice, proposal=proposal, status="IN_PROGRESS")
    otis.login("alice")
    resp = otis.post(
        "oime-proposal-detail",
        proposal.pk,
        data={"submit_comment": "1", "content": "Spoiler!"},
    )
    assert resp.status_code == 403
    assert not OIMEComment.objects.exists()
