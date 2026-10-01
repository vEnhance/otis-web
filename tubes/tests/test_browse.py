from datetime import timedelta

import pytest
from django.utils import timezone

from core.factories import UserFactory
from tubes.factories import (
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
)
from tubes.models import OIMEComment, OIMEFight
from tubes.views import BROWSE_PAGE_SIZE

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Casual mode / solution reveal logic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ranked_hides_solution(otis):
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # Pre-fight, a ranked solver sees only the start screen, never the solution.
    resp = otis.get_20x("oime-start-fight", proposal.pk)
    assert resp.context["can_start_fight"]
    assert not resp.context["can_see_solution"]


@pytest.mark.django_db
def test_start_screen_redirects_when_cannot_fight(otis):
    # Someone who already finished a fight can't use the start screen → back to detail.
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
def test_solution_offered_as_tex_download_and_mathjax_preview(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create()
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    otis.assert_testid(resp, "solution-tex-link")
    otis.assert_testid(resp, "solution-preview")
    otis.assert_has(resp, otis.url("oime-proposal-solution-tex", proposal.pk))


@pytest.mark.django_db
def test_solution_tex_download(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(
        answer=42,
        statement="Compute $1+1$.",
        solution="Clearly $1+1=2$.",
    )
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_OK"
    )
    otis.login(user)
    # The response body is the product here, so the bytes really are the contract.
    resp = otis.get_20x("oime-proposal-solution-tex", proposal.pk)
    assert resp.headers["Content-Disposition"] == (
        f'attachment; filename="oime-{proposal.label}.tex"'
    )
    otis.assert_has(resp, "Compute $1+1$.")
    otis.assert_has(resp, "42")
    otis.assert_has(resp, "Clearly $1+1=2$.")


@pytest.mark.django_db
def test_solution_tex_denied_before_solution_is_visible(otis):
    user, contributor = verified_contributor()
    proposal = OIMEProposalFactory.create(solution="Secret solution.")
    otis.login(user)
    # Ranked, never fought: the answer and solution are still under lock.
    resp = otis.get_40x("oime-proposal-solution-tex", proposal.pk)
    otis.assert_not_has(resp, "Secret solution.")
    # An active fight is no better; the file carries the answer.
    OIMEFightFactory.create(
        contributor=contributor, proposal=proposal, status="OIME_TBD"
    )
    resp = otis.get_40x("oime-proposal-solution-tex", proposal.pk)
    otis.assert_not_has(resp, "Secret solution.")


@pytest.mark.django_db
def test_solution_tex_denied_on_archived_problem(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMEProposalFactory.create(author=other, archived=True)
    otis.login(user)
    otis.get_40x("oime-proposal-solution-tex", proposal.pk)


@pytest.mark.django_db
def test_cannot_reveal_during_active_fight(otis):
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
    otis.login(user)
    resp = otis.post("oime-casual")
    otis.assert_30x(resp)
    contributor.refresh_from_db()
    assert contributor.casual_mode is True


@pytest.mark.django_db
def test_casual_completed_fight_shows_as_solved(otis):
    # A casual solver who completed a fight earlier should see the recorded result
    # ("MM:SS (✖N)"), not "Try it" (regression for a list/detail mismatch).
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
    user, contributor = verified_contributor()
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
# Per-subject full-statement browser
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_subject_browse_shows_statements_of_one_subject(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    wanted = OIMEProposalFactory.create(subject="G", statement="Geometry statement.")
    other_subject = OIMEProposalFactory.create(subject="N", statement="Number theory.")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G")
    assert list(resp.context["page_obj"]) == [wanted]
    assert other_subject not in resp.context["page_obj"]
    # this browser exists to put whole statements on the page, so that is content
    otis.assert_has(resp, "Geometry statement.")
    otis.assert_not_has(resp, "Number theory.")


@pytest.mark.django_db
def test_subject_browse_never_shows_answers_or_solutions(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="A", answer=123, solution="Secret solution.")
    otis.login(user)
    # bulk browse has no per-proposal solver context; the page must simply never
    # carry a solution, so this stays a leakage check on the bytes
    resp = otis.get_20x("oime-subject-browse", "A")
    otis.assert_not_has(resp, "Secret solution.")


@pytest.mark.django_db
def test_subject_browse_includes_spoiled_problems_but_marks_them(otis):
    user, contributor = verified_contributor()
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
    resp = otis.get_20x("oime-subject-browse", "C")
    # Every problem is listed, but each is labelled by how the viewer has
    # already engaged with it.
    statuses = {p.pk: p.user_list_status for p in resp.context["page_obj"]}
    assert statuses == {
        fresh.pk: "casual",
        own.pk: "author",
        revealed.pk: "revealed",
        solved.pk: "completed",
        gave_up.pk: "completed",
    }
    spoiled = {p.pk for p in resp.context["page_obj"] if p.spoiled}
    assert spoiled == {own.pk, revealed.pk, solved.pk, gave_up.pk}


@pytest.mark.django_db
def test_subject_browse_hides_archived_and_drafts(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="N", archived=True, statement="Archived one.")
    OIMEProposalFactory.create(subject="N", is_draft=True, statement="Draft one.")
    # Even the viewer's own draft stays out; drafts live on the drafts page only.
    OIMEProposalFactory.create(
        author=contributor, subject="N", is_draft=True, statement="My draft."
    )
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "N")
    assert list(resp.context["page_obj"]) == []


@pytest.mark.django_db
def test_subject_browse_orders_newest_first(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    oldest = OIMEProposalFactory.create(subject="A")
    middle = OIMEProposalFactory.create(subject="A")
    newest = OIMEProposalFactory.create(subject="A")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A")
    assert list(resp.context["page_obj"]) == [newest, middle, oldest]


@pytest.mark.django_db
def test_subject_browse_sorts_by_votes_on_request(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    unloved = OIMEProposalFactory.create(subject="A")
    beloved = OIMEProposalFactory.create(subject="A")
    liked = OIMEProposalFactory.create(subject="A")
    for _ in range(3):
        beloved.upvotes.add(OIMEContributorFactory.create())
    liked.upvotes.add(OIMEContributorFactory.create())
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A", data={"sort": "votes"})
    assert list(resp.context["page_obj"]) == [beloved, liked, unloved]
    # Without the parameter the browser is still newest-first.
    resp = otis.get_20x("oime-subject-browse", "A")
    assert list(resp.context["page_obj"]) == [liked, beloved, unloved]


@pytest.mark.django_db
def test_subject_browse_filters_by_difficulty(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    easy = OIMEProposalFactory.create(subject="C", difficulty=1)
    hard = OIMEProposalFactory.create(subject="C", difficulty=5)
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "C", data={"difficulty": 5})
    assert list(resp.context["page_obj"]) == [hard]
    assert resp.context["difficulty"] == 5
    resp = otis.get_20x("oime-subject-browse", "C", data={"difficulty": 1})
    assert list(resp.context["page_obj"]) == [easy]
    resp = otis.get_20x("oime-subject-browse", "C")
    assert list(resp.context["page_obj"]) == [hard, easy]
    assert resp.context["difficulty"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("raw", ["0", "6", "banana", ""])
def test_subject_browse_ignores_bogus_difficulty(otis, raw: str):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create(subject="G", difficulty=2)
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G", data={"difficulty": raw})
    assert list(resp.context["page_obj"]) == [proposal]
    assert resp.context["difficulty"] is None


@pytest.mark.django_db
def test_subject_browse_controls_carry_settings(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "N")
    otis.assert_testid(resp, "browse-sort-toggle")
    otis.assert_testid(resp, "browse-difficulty-filter")
    assert resp.context["browse_params"] == ""
    assert resp.context["sort_toggle_params"] == "sort=votes"

    # Each control keeps whatever the other one is set to.
    resp = otis.get_20x(
        "oime-subject-browse", "N", data={"sort": "votes", "difficulty": 4}
    )
    assert resp.context["browse_params"] == "sort=votes&difficulty=4"
    assert resp.context["sort_toggle_params"] == "difficulty=4"
    options = resp.context["difficulty_options"]
    assert [o["value"] for o in options] == [None, 1, 2, 3, 4, 5]
    assert [o["params"] for o in options] == [
        "sort=votes",
        "sort=votes&difficulty=1",
        "sort=votes&difficulty=2",
        "sort=votes&difficulty=3",
        "sort=votes&difficulty=4",
        "sort=votes&difficulty=5",
    ]
    assert [o["selected"] for o in options] == [False] * 4 + [True, False]

    # With no filter on, the dropdown marks "All" as the selected entry.
    resp = otis.get_20x("oime-subject-browse", "N")
    assert [o["selected"] for o in resp.context["difficulty_options"]] == [True] + [
        False
    ] * 5


@pytest.mark.django_db
def test_subject_browse_difficulty_badges_toggle_the_filter(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="A", difficulty=2)
    OIMEProposalFactory.create(subject="A", difficulty=4)
    otis.login(user)

    # Unfiltered, each badge links to its own difficulty, keeping the sort.
    resp = otis.get_20x("oime-subject-browse", "A", data={"sort": "votes"})
    assert [p.difficulty_params for p in resp.context["page_obj"]] == [
        "sort=votes&difficulty=4",
        "sort=votes&difficulty=2",
    ]

    # The badge of the difficulty already filtered on clears the filter instead.
    resp = otis.get_20x("oime-subject-browse", "A", data={"difficulty": 4})
    assert [p.difficulty_params for p in resp.context["page_obj"]] == [""]
    otis.assert_testid(resp, "browse-difficulty-badge", count=1)


@pytest.mark.django_db
def test_subject_browse_marks_upvoted_problems(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    hearted = OIMEProposalFactory.create(subject="A")
    OIMEProposalFactory.create(subject="A")
    # Someone else's upvote must not light up the badge for this contributor.
    OIMEProposalFactory.create(subject="A").upvotes.add(OIMEContributorFactory.create())
    hearted.upvotes.add(contributor)
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A")
    assert [p.has_upvoted for p in resp.context["page_obj"]] == [False, False, True]
    otis.assert_testid(resp, "browse-upvoted", count=1)


@pytest.mark.django_db
def test_subject_browse_paginates(otis):

    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposals = [
        OIMEProposalFactory.create(subject="G") for _ in range(BROWSE_PAGE_SIZE + 3)
    ]
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G")
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.num_pages == 2
    assert len(page_obj.object_list) == BROWSE_PAGE_SIZE
    assert list(page_obj) == list(reversed(proposals))[:BROWSE_PAGE_SIZE]
    resp = otis.get_20x("oime-subject-browse", "G", data={"page": 2})
    page_obj = resp.context["page_obj"]
    assert list(page_obj) == list(reversed(proposals))[BROWSE_PAGE_SIZE:]
    # Statuses are still computed on later pages.
    assert all(p.user_list_status == "casual" for p in page_obj)


@pytest.mark.django_db
def test_subject_browse_bad_page_falls_back_to_first(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    OIMEProposalFactory.create(subject="G")
    otis.login(user)
    for bad_page in ("0", "99", "banana"):
        resp = otis.get_20x("oime-subject-browse", "G", data={"page": bad_page})
        assert resp.context["page_obj"].number == 1


@pytest.mark.django_db
def test_subject_browse_locks_unopened_problems_in_ranked_mode(otis):
    # Ranked statements are meant to be read for the first time under the clock, so
    # the browser is open to ranked contributors but holds back what they have not
    # started yet.
    user, contributor = verified_contributor()
    unopened = OIMEProposalFactory.create(subject="G", statement="Still secret.")
    opened = OIMEProposalFactory.create(subject="G", statement="Already fought this.")
    OIMEFightFactory.create(contributor=contributor, proposal=opened, status="OIME_OK")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G")
    assert {p.pk: p.locked for p in resp.context["page_obj"]} == {
        unopened.pk: True,
        opened.pk: False,
    }
    # A locked statement must not reach the page at all, so this is a leakage check.
    otis.assert_not_has(resp, "Still secret.")
    otis.assert_has(resp, "Already fought this.")
    otis.assert_testid(resp, "browse-locked", count=1)


@pytest.mark.django_db
def test_subject_browse_unlocks_what_ranked_mode_no_longer_covers(otis):
    # Everything a ranked contributor can no longer fight is readable: their own
    # problems, ones they revealed, ones they have an open session on, and ones that
    # went casual for them when they last came back to ranked mode.
    user, contributor = verified_contributor()
    own = OIMEProposalFactory.create(author=contributor, subject="A")
    revealed = OIMEProposalFactory.create(subject="A")
    contributor.revealed_proposals.add(revealed)
    in_progress = OIMEProposalFactory.create(subject="A")
    OIMEFightFactory.create(
        contributor=contributor, proposal=in_progress, status="OIME_TBD"
    )
    before_cutoff = OIMEProposalFactory.create(subject="A")
    contributor.ranked_cutoff = timezone.now()
    contributor.save()
    after_cutoff = OIMEProposalFactory.create(subject="A")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A")
    assert {p.pk: p.locked for p in resp.context["page_obj"]} == {
        own.pk: False,
        revealed.pk: False,
        in_progress.pk: False,
        before_cutoff.pk: False,
        after_cutoff.pk: True,
    }


@pytest.mark.django_db
def test_subject_browse_locked_problems_cannot_be_voted_on(otis):
    # The heart is the one control on a locked card that would do something, and a
    # misclick there would be easy; the view refuses the vote either way.
    user, _ = verified_contributor()
    locked = OIMEProposalFactory.create(subject="N")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "N")
    assert [p.locked for p in resp.context["page_obj"]] == [True]
    otis.assert_not_has(resp, otis.url("oime-upvote", locked.pk))
    resp = otis.post("oime-upvote", locked.pk, data={"back_subject": "N"})
    assert resp.status_code == 403
    assert locked.upvotes.count() == 0


@pytest.mark.django_db
def test_subject_browse_shows_the_verdict_of_a_finished_fight(otis):
    # The card footer says what happened, the same way the listing tables do,
    # instead of the generic "you are spoiled on this" line.
    user, contributor = verified_contributor()
    solved = OIMEProposalFactory.create(subject="C")
    OIMEFightFactory.create(contributor=contributor, proposal=solved, status="OIME_OK")
    gave_up = OIMEProposalFactory.create(subject="C")
    OIMEFightFactory.create(
        contributor=contributor, proposal=gave_up, status="OIME_FAIL"
    )
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "C")
    otis.assert_testid(resp, "verdict-solved", count=1)
    otis.assert_testid(resp, "verdict-gave-up", count=1)


@pytest.mark.django_db
def test_subject_browse_keeps_casual_footer_messages(otis):
    # A casual browser who never fought the problem still gets the old wording.
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    fresh = OIMEProposalFactory.create(subject="G")
    revealed = OIMEProposalFactory.create(subject="G")
    contributor.revealed_proposals.add(revealed)
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G")
    assert {p.pk: p.user_list_status for p in resp.context["page_obj"]} == {
        fresh.pk: "casual",
        revealed.pk: "revealed",
    }
    # Nothing is locked in casual mode, so every statement is on the page.
    otis.assert_no_testid(resp, "browse-locked")


@pytest.mark.django_db
def test_subject_browse_filters_by_lock_state(otis):
    user, contributor = verified_contributor()
    # A problem that predates their return to ranked mode is browse-only for them,
    # so it counts as unlocked however untouched it is.
    before_cutoff = OIMEProposalFactory.create(subject="N")
    contributor.ranked_cutoff = timezone.now()
    contributor.save()
    locked = OIMEProposalFactory.create(subject="N")
    unlocked = OIMEProposalFactory.create(subject="N")
    OIMEFightFactory.create(
        contributor=contributor, proposal=unlocked, status="OIME_OK"
    )
    mine = OIMEProposalFactory.create(author=contributor, subject="N")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "N", data={"lock": "locked"})
    assert set(resp.context["page_obj"]) == {locked}
    assert resp.context["lock"] == "locked"
    resp = otis.get_20x("oime-subject-browse", "N", data={"lock": "unlocked"})
    assert set(resp.context["page_obj"]) == {unlocked, mine, before_cutoff}
    resp = otis.get_20x("oime-subject-browse", "N")
    assert set(resp.context["page_obj"]) == {locked, unlocked, mine, before_cutoff}
    assert resp.context["lock"] is None
    # The filter and the per-card lock flag are two readings of the same rule.
    assert {p.pk for p in resp.context["page_obj"] if p.locked} == {locked.pk}


@pytest.mark.django_db
@pytest.mark.parametrize("raw", ["", "open", "1"])
def test_subject_browse_ignores_bogus_lock(otis, raw: str):
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create(subject="G")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "G", data={"lock": raw})
    assert list(resp.context["page_obj"]) == [proposal]
    assert resp.context["lock"] is None


@pytest.mark.django_db
def test_subject_browse_hides_the_lock_filter_in_casual_mode(otis):
    # Nothing is ever locked in casual mode, so the filter would only be a way to
    # ask for an empty page.
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    proposal = OIMEProposalFactory.create(subject="A")
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A", data={"lock": "locked"})
    assert resp.context["lock_options"] is None
    assert resp.context["lock"] is None
    assert list(resp.context["page_obj"]) == [proposal]
    otis.assert_no_testid(resp, "browse-lock-filter")


@pytest.mark.django_db
@pytest.mark.parametrize("casual_mode", [True, False])
def test_subject_browse_offers_the_mode_switch(otis, casual_mode: bool):
    # The mode is what decides whether anything on this page is locked, so the way
    # to change it belongs here too.
    user, contributor = verified_contributor()
    contributor.casual_mode = casual_mode
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A")
    wanted = "oime-serious" if casual_mode else "oime-casual"
    otis.assert_has(resp, otis.url(wanted))


@pytest.mark.django_db
def test_subject_browse_lock_filter_offered_in_ranked_mode(otis):
    user, _ = verified_contributor()
    otis.login(user)
    resp = otis.get_20x("oime-subject-browse", "A")
    otis.assert_testid(resp, "browse-lock-filter")
    options = resp.context["lock_options"]
    assert [o["value"] for o in options] == [None, "locked", "unlocked"]
    assert [o["params"] for o in options] == ["", "lock=locked", "lock=unlocked"]


@pytest.mark.django_db
def test_subject_browse_rejects_unknown_subject(otis):
    user, contributor = verified_contributor()
    contributor.casual_mode = True
    contributor.save()
    otis.login(user)
    otis.get_not_found("oime-subject-browse", "Z")


@pytest.mark.django_db
def test_subject_browse_requires_verification(otis):
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-subject-browse", "G")


@pytest.mark.django_db
@pytest.mark.parametrize("casual_mode", [True, False])
def test_all_problems_always_links_to_every_subject(otis, casual_mode: bool):
    # The subject browser is useful in both modes now, so its four buttons are part
    # of the navigation rather than a casual-only extra.
    user, contributor = verified_contributor()
    contributor.casual_mode = casual_mode
    contributor.save()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert resp.context["casual"] is casual_mode
    for code in ("A", "C", "G", "N"):
        otis.assert_has(resp, otis.url("oime-subject-browse", code))
    otis.assert_has(resp, otis.url("oime-landing"))
