from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from core.factories import UserFactory
from tubes.factories import OIMEFightFactory, OIMEProposalFactory
from tubes.models import OIMEFight, OIMEProposal
from tubes.views import LANDING_RECENT_COUNT

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Landing page: recovering an abandoned timed session
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_landing_links_to_active_fight(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(difficulty=5)
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["active_fight"].proposal == proposal


@pytest.mark.django_db
def test_landing_marks_abandoned_fight_as_tle(otis):
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["active_fight"] is None


@pytest.mark.django_db
def test_landing_requires_login(otis):
    otis.assert_30x(otis.get("oime-landing"))
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-landing")


# ---------------------------------------------------------------------------
# Landing page: the newest problems and your own
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_landing_shows_the_five_newest_problems(otis):

    user, _ = verified_contributor()
    proposals = [OIMEProposalFactory.create() for _ in range(LANDING_RECENT_COUNT + 2)]
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert (
        resp.context["recent_proposals"]
        == list(reversed(proposals))[:LANDING_RECENT_COUNT]
    )


@pytest.mark.django_db
def test_landing_newest_omits_drafts_and_archived(otis):
    user, contributor = verified_contributor()
    published = OIMEProposalFactory.create()
    OIMEProposalFactory.create(is_draft=True)
    OIMEProposalFactory.create(archived=True)
    # Even the viewer's own draft stays out of the public list; it belongs under
    # "Your problems" instead.
    OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["recent_proposals"] == [published]


@pytest.mark.django_db
def test_landing_shows_own_proposals_and_drafts(otis):
    user, contributor = verified_contributor()
    _, other = verified_contributor("bob")
    published = OIMEProposalFactory.create(author=contributor)
    draft = OIMEProposalFactory.create(author=contributor, is_draft=True)
    OIMEProposalFactory.create(author=contributor, archived=True)
    OIMEProposalFactory.create()  # somebody else's
    OIMEProposalFactory.create(author=other, is_draft=True, title="Bob's draft")
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert set(resp.context["own_proposals"]) == {published, draft}
    otis.assert_not_has(resp, "Bob's draft")
    assert all(p.user_list_status == "author" for p in resp.context["own_proposals"])
    # The status column names which is which. The published one is also in the
    # "newest problems" table above, so it is rendered twice; the draft is not,
    # since drafts are nobody else's business.
    otis.assert_testid(resp, "table-published", count=2)
    otis.assert_testid(resp, "table-draft", count=1)


@pytest.mark.django_db
def test_landing_links_to_every_subject_and_all_problems(otis):
    user, _ = verified_contributor()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    for code in ("A", "C", "G", "N"):
        otis.assert_has(resp, otis.url("oime-subject-browse", code))
    otis.assert_has(resp, otis.url("oime-proposal-list"))
    otis.assert_has(resp, otis.url("oime-proposal-create"))
    otis.assert_has(resp, otis.url("oime-setup"))


@pytest.mark.django_db
def test_landing_offers_onboarding_without_a_contributor(otis):
    # None of the tables mean anything without a profile, so the one thing on offer
    # is making one.
    OIMEProposalFactory.create(title="Somebody's problem")
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="bob", groups=(verified_group,))
    otis.login("bob")
    resp = otis.get_20x("oime-landing")
    assert resp.context["contributor"] is None
    assert "recent_proposals" not in resp.context
    otis.assert_not_has(resp, "Somebody's problem")
    otis.assert_has(resp, otis.url("oime-setup"))
    otis.assert_not_has(resp, otis.url("oime-proposal-create"))


@pytest.mark.django_db
def test_landing_newest_table_carries_the_viewers_own_status(otis):
    user, contributor = verified_contributor()
    solved = OIMEProposalFactory.create()
    OIMEFightFactory.create(contributor=contributor, proposal=solved, status="OIME_OK")
    OIMEProposalFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert {p.pk: p.user_list_status for p in resp.context["recent_proposals"]} == {
        solved.pk: "completed",
        OIMEProposal.objects.exclude(pk=solved.pk).get().pk: "not_started",
    }
    otis.assert_testid(resp, "verdict-solved", count=1)
