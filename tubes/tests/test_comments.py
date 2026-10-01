from datetime import timedelta

import pytest

from core.factories import UserFactory
from tubes.factories import (
    OIMECommentFactory,
    OIMEContributorFactory,
    OIMEProposalFactory,
)
from tubes.models import OIMEComment

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Comment editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_author_can_edit_own_comment(otis):
    user, contributor = verified_contributor()
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
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
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
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(author=contributor)
    OIMECommentFactory.create(author=contributor, proposal=proposal, content="Hi")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_no_testid(resp, "comment-edited")


@pytest.mark.django_db
def test_edited_label_shown_after_meaningful_edit(otis):
    user, contributor = verified_contributor()
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
# "Author" badge on comments written by the problem's author
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_author_badge_shown_only_for_problem_author_comments(otis):
    user, contributor = verified_contributor()
    other = OIMEContributorFactory.create(user=UserFactory.create(username="bob"))
    proposal = OIMEProposalFactory.create(author=contributor)
    OIMECommentFactory.create(author=contributor, proposal=proposal, content="Mine")
    OIMECommentFactory.create(author=other, proposal=proposal, content="Theirs")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_has(resp, ">Author</span>", count=1)


@pytest.mark.django_db
def test_author_badge_absent_when_author_has_not_commented(otis):
    user, contributor = verified_contributor()
    author = OIMEContributorFactory.create(user=UserFactory.create(username="bob"))
    proposal = OIMEProposalFactory.create(author=author)
    contributor.casual_mode = True
    contributor.save()
    contributor.revealed_proposals.add(proposal)
    OIMECommentFactory.create(author=contributor, proposal=proposal, content="Nice")
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_not_has(resp, ">Author</span>")
