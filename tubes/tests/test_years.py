import io
import zipfile
from datetime import timedelta

import pytest
from django.utils import timezone

from tubes.factories import (
    OIMEContributorFactory,
    OIMEFightFactory,
    OIMEProposalFactory,
    OIMESelectionFactory,
    OIMEYearFactory,
)
from tubes.models import OIMEProposal

from .helpers import verified_admin, verified_contributor, verified_staff

PROPOSAL_DATA = {
    "title": "Squares",
    "statement": "Find all $x$ such that $x^2 = 4$.",
    "answer": 2,
    "solution": "Clearly $x = \\pm 2$.",
    "subject": "A",
    "difficulty": 1,
}


def closed_year(**kwargs):
    """A year whose proposal window closed yesterday."""
    now = timezone.now()
    return OIMEYearFactory.create(
        proposals_open_at=now - timedelta(days=30),
        proposals_close_at=now - timedelta(days=1),
        **kwargs,
    )


def released_year(**kwargs):
    return closed_year(release_at=timezone.now() - timedelta(hours=1), **kwargs)


# ---------------------------------------------------------------------------
# Submission window
# ---------------------------------------------------------------------------


def update_data(**kwargs):
    """Form data for editing a proposal; difficulty is fixed after creation."""
    data = {**PROPOSAL_DATA, **kwargs}
    data.pop("difficulty")
    return data


@pytest.mark.django_db
def test_create_form_defaults_to_draft_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.get_20x("oime-proposal-create")
    assert resp.context["form"].initial["is_draft"] is True


@pytest.mark.django_db
def test_create_published_blocked_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.post("oime-proposal-create", data=PROPOSAL_DATA)
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    assert OIMEProposal.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_allowed_without_open_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    otis.post_30x("oime-proposal-create", data={**PROPOSAL_DATA, "is_draft": True})
    assert OIMEProposal.objects.get().is_draft is True


@pytest.mark.django_db
def test_create_allowed_during_window(otis):
    user, _ = verified_contributor()
    OIMEYearFactory.create()
    otis.login(user)
    otis.post_30x("oime-proposal-create", data=PROPOSAL_DATA)
    assert OIMEProposal.objects.get().is_draft is False


@pytest.mark.django_db
def test_staff_may_create_outside_window(otis):
    staff, _ = verified_staff()
    closed_year()
    otis.login(staff)
    otis.post_30x("oime-proposal-create", data=PROPOSAL_DATA)
    assert OIMEProposal.objects.get().is_draft is False


@pytest.mark.django_db
def test_publishing_a_draft_blocked_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update", proposal.pk, data=update_data(is_draft=False)
    )
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    proposal.refresh_from_db()
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_editing_a_draft_allowed_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data(is_draft=True))
    proposal.refresh_from_db()
    assert proposal.title == "Squares"
    assert proposal.is_draft is True


@pytest.mark.django_db
def test_unpublishing_blocked_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=False)
    otis.login(user)
    resp = otis.post(
        "oime-proposal-update", proposal.pk, data=update_data(is_draft=True)
    )
    assert resp.status_code == 200
    assert "is_draft" in resp.context["form"].errors
    proposal.refresh_from_db()
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_editing_a_published_problem_allowed_without_open_window(otis):
    user, contributor = verified_contributor()
    closed_year()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=False)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data())
    proposal.refresh_from_db()
    assert proposal.title == "Squares"
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_publishing_a_draft_during_window(otis):
    user, contributor = verified_contributor()
    OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create(author=contributor, is_draft=True)
    otis.login(user)
    otis.post_30x("oime-proposal-update", proposal.pk, data=update_data(is_draft=False))
    proposal.refresh_from_db()
    assert proposal.is_draft is False


@pytest.mark.django_db
def test_landing_shows_deadline_when_open(otis):
    user, _ = verified_contributor()
    year = OIMEYearFactory.create()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["accepting_year"] == year
    otis.assert_testid(resp, "proposals-open-note")


@pytest.mark.django_db
def test_landing_shows_closed_without_window(otis):
    user, _ = verified_contributor()
    closed_year()
    otis.login(user)
    resp = otis.get_20x("oime-landing")
    assert resp.context["accepting_year"] is None
    otis.assert_testid(resp, "proposals-closed-note")


# ---------------------------------------------------------------------------
# Pool, freezing and retirement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_in_pool_excludes_only_retired():
    plain = OIMEProposalFactory.create()
    shortlisted = OIMESelectionFactory.create().proposal
    deferred_released = OIMESelectionFactory.create(
        year=released_year(), status="SEL_DEFERRED"
    ).proposal
    retired = OIMESelectionFactory.create(
        year=released_year(), status="SEL_DONE"
    ).proposal
    pool = set(OIMEProposal.in_pool())
    assert {plain, shortlisted, deferred_released} <= pool
    assert retired not in pool
    assert retired.is_retired is True
    assert deferred_released.is_retired is False


@pytest.mark.django_db
def test_retired_problem_is_hidden_and_frozen(otis):
    user, _ = verified_contributor()
    _, other = verified_contributor("bob")
    proposal = OIMESelectionFactory.create(
        year=released_year(), proposal__author=other
    ).proposal
    otis.login(user)
    resp = otis.get_20x("oime-proposal-list")
    assert proposal not in resp.context["proposals"]
    otis.get_40x("oime-proposal-detail", proposal.pk)
    otis.post_40x("oime-start-fight", proposal.pk)


@pytest.mark.django_db
def test_retired_problem_readable_by_author_but_frozen(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(
        year=released_year(), proposal__author=contributor
    ).proposal
    otis.login(user)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_upvote"] is False
    assert resp.context["can_comment"] is False
    otis.assert_testid(resp, "proposal-retired-note")


@pytest.mark.django_db
def test_selected_problem_locks_author_edits(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(proposal__author=contributor).proposal
    otis.login(user)
    otis.get_40x("oime-proposal-update", proposal.pk)
    resp = otis.get_20x("oime-proposal-detail", proposal.pk)
    assert resp.context["can_edit"] is False
    otis.assert_no_testid(resp, "proposal-edit-link")


@pytest.mark.django_db
def test_deferred_problem_stays_editable(otis):
    user, contributor = verified_contributor()
    proposal = OIMESelectionFactory.create(
        proposal__author=contributor, status="SEL_DEFERRED"
    ).proposal
    otis.login(user)
    otis.get_20x("oime-proposal-update", proposal.pk)


@pytest.mark.django_db
def test_staff_may_edit_selected_problem(otis):
    staff, _ = verified_staff()
    proposal = OIMESelectionFactory.create().proposal
    otis.login(staff)
    otis.get_20x("oime-proposal-update", proposal.pk)


# ---------------------------------------------------------------------------
# Exports: the bytes are the product here
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_exports_are_admin_only(otis):
    staff, _ = verified_staff()
    year = OIMEYearFactory.create()
    otis.login(staff)
    otis.get_40x("oime-year-export", year.pk)
    otis.get_40x("oime-year-descriptions", year.pk)


@pytest.mark.django_db
def test_export_zip_has_house_format(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    author = OIMEContributorFactory.create(display_name="Jiahe Liu")
    proposal = OIMEProposalFactory.create(
        author=author,
        subject="C",
        title="i <3 u",
        statement="Count pairs.",
        answer=41,
        solution="Use Pick's theorem.",
    )
    OIMESelectionFactory.create(
        year=year, proposal=proposal, status="SEL_DONE", description="$i <3 u$"
    )
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    solver = OIMEContributorFactory.create(display_name="Tester Ann")
    OIMEFightFactory.create(contributor=solver, proposal=proposal, status="OIME_OK")
    # An unfinished fight on some other problem must not drop a testsolver.
    OIMEFightFactory.create(contributor=solver, status="OIME_TBD")
    bystander = OIMEContributorFactory.create(display_name="Only Started")
    OIMEFightFactory.create(contributor=bystander, proposal=proposal, status="OIME_TBD")
    shy = OIMEContributorFactory.create(
        display_name="Shy Solver", hide_from_acknowledgments=True
    )
    OIMEFightFactory.create(contributor=shy, proposal=proposal, status="OIME_OK")

    otis.login(admin)
    resp = otis.get_20x("oime-year-export", year.pk)
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    assert sorted(archive.namelist()) == [
        "data/solves.tex",
        "data/testsolving.tex",
        f"originals/{proposal.label}.tex",
        f"problems/{proposal.label}.tex",
        "problems/acknow.tex",
        "problems/order1.tex",
    ]
    tex = archive.read(f"problems/{proposal.label}.tex").decode()
    assert (
        "\\shortdesc{$i <3 u$}\n\\begin{problem}\n  Count pairs.\n\\end{problem}" in tex
    )
    assert "\\answer{041}" in tex
    assert "\\credits{Jiahe Liu}" in tex
    assert "\\begin{soln}\n  Use Pick's theorem.\n\\end{soln}" in tex
    assert otis.url("oime-proposal-detail", proposal.pk) in tex

    order = archive.read("problems/order1.tex").decode()
    assert f"\\input{{problems/{proposal.label}}}  % [C] $i <3 u$" in order
    assert archive.read(f"originals/{proposal.label}.tex") == b"Count pairs.\n"

    acknow = archive.read("problems/acknow.tex").decode()
    assert "Jiahe Liu," in acknow
    assert "Tester Ann,  % 1 problems" in acknow
    assert "Shy Solver" not in acknow
    assert "Only Started" not in acknow


@pytest.mark.django_db
def test_export_description_defaults_to_escaped_title(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    proposal = OIMEProposalFactory.create(title="50% off")
    OIMESelectionFactory.create(year=year, proposal=proposal)
    otis.login(admin)
    archive = zipfile.ZipFile(
        io.BytesIO(otis.get_20x("oime-year-export", year.pk).content)
    )
    tex = archive.read(f"problems/{proposal.label}.tex").decode()
    assert "\\shortdesc{50\\% off}" in tex


@pytest.mark.django_db
def test_export_stats(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    solved = OIMEProposalFactory.create()
    unsolved = OIMEProposalFactory.create()
    OIMESelectionFactory.create(year=year, proposal=solved)
    OIMESelectionFactory.create(year=year, proposal=unsolved)
    fast = OIMEFightFactory.create(proposal=solved, status="OIME_OK")
    fast.submitted_at = fast.started_at + timedelta(seconds=75)
    fast.save()
    slow = OIMEFightFactory.create(proposal=solved, status="OIME_OK")
    solved.upvotes.add(slow.contributor)
    slow.submitted_at = slow.started_at + timedelta(seconds=125)
    slow.save()
    OIMEFightFactory.create(
        proposal=solved, status="OIME_OK", wrong_answers=1, submitted_at=timezone.now()
    )
    OIMEFightFactory.create(proposal=solved, status="OIME_FAIL")
    OIMEFightFactory.create(proposal=unsolved, status="OIME_FAIL")

    otis.login(admin)
    archive = zipfile.ZipFile(
        io.BytesIO(otis.get_20x("oime-year-export", year.pk).content)
    )
    stats = archive.read("data/testsolving.tex").decode()
    assert (
        f"\\oimetestsolving{{{solved.label}}}{{1:15}}{{1:40}}{{2}}{{3}}{{4}}{{1}}"
        in stats
    )
    assert (
        f"\\oimetestsolving{{{unsolved.label}}}{{---}}{{---}}{{0}}{{0}}{{1}}{{0}}"
        in stats
    )
    solves = archive.read("data/solves.tex").decode()
    assert f"%\\oimesolves{{{solved.label}}}{{}}" in solves
    assert "%\\oimescore{2}{}" in solves


@pytest.mark.django_db
def test_descriptions_lists_only_chosen(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    chosen = OIMESelectionFactory.create(year=year)
    OIMESelectionFactory.create(year=year, status="SEL_DEFERRED")
    OIMESelectionFactory.create()
    otis.login(admin)
    resp = otis.get_20x("oime-year-descriptions", year.pk)
    assert [f.instance for f in resp.context["formset"]] == [chosen]


@pytest.mark.django_db
def test_descriptions_bulk_save(otis):
    admin, _ = verified_admin()
    year = OIMEYearFactory.create()
    first = OIMESelectionFactory.create(year=year)
    second = OIMESelectionFactory.create(year=year, description="old")
    otis.login(admin)
    otis.post_redirects(
        otis.url("oime-year-descriptions", year.pk),
        "oime-year-descriptions",
        year.pk,
        data={
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-0-id": str(first.pk),
            "form-0-description": "$3n$ and $4n$",
            "form-1-id": str(second.pk),
            "form-1-description": "",
        },
    )
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.description == "$3n$ and $4n$"
    assert second.description == ""
