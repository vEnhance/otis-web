import os

import pytest
from django.conf import settings
from django.contrib.messages import constants as message_levels
from django.http import Http404
from django.test import override_settings
from django.urls import reverse

from arch.factories import HintFactory, ProblemFactory
from arch.models import Hint, Problem, Vote
from arch.utils import get_disk_statement_from_puid, validate_puid
from core.factories import GroupFactory, UserFactory
from core.models import UserProfile


@pytest.mark.django_db
@override_settings(
    PATH_STATEMENT_ON_DISK=os.path.join(settings.BASE_DIR, "test_static/")
)
def test_disk_problem(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    disk_puid = "STUPID"

    if not os.path.exists(settings.PATH_STATEMENT_ON_DISK):
        os.makedirs(settings.PATH_STATEMENT_ON_DISK)

    html_path = os.path.join(settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.html")
    tex_path = os.path.join(settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.tex")

    with open(html_path, "w", encoding="utf_8") as f:
        f.write("<p>rock and roll</p>")
    with open(tex_path, "w", encoding="utf_8") as f:
        f.write(r"Show that $x < y$ \emph{rocks and rolls}.")

    otis.get_40x("hint-list", "NONEXISTENT")
    resp = otis.get_20x("hint-list", disk_puid)

    # the problem row is created on demand, and the student is told so
    assert Problem.objects.filter(puid=disk_puid).exists()
    assert any(m.level == message_levels.INFO for m in resp.context["messages"])

    # the HTML statement is rendered as-is, the TeX source is shown escaped
    otis.assert_has(resp, "<p>rock and roll</p>")
    otis.assert_has(resp, r"Show that $x &lt; y$ \emph{rocks and rolls}.")

    # the PUID is used verbatim: uppercasing inside the lookup would let
    # view_solution pass this check and then 500 on the lowercase solution.
    # (skipped when the filesystem itself is case-insensitive)
    lower_path = os.path.join(
        settings.PATH_STATEMENT_ON_DISK, f"{disk_puid.lower()}.html"
    )
    if not os.path.exists(lower_path):
        assert get_disk_statement_from_puid(disk_puid.lower()) is None
        otis.get_40x("view-solution", disk_puid.lower())

    os.remove(html_path)
    os.remove(tex_path)
    if not os.listdir(settings.PATH_STATEMENT_ON_DISK):
        os.rmdir(settings.PATH_STATEMENT_ON_DISK)


@pytest.mark.django_db
@override_settings(
    PATH_STATEMENT_ON_DISK=os.path.join(settings.BASE_DIR, "test_static/")
)
def test_disk_statement_missing_tex(otis):
    """An HTML statement with no TeX source next to it should still render."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    disk_puid = "LONELY"

    if not os.path.exists(settings.PATH_STATEMENT_ON_DISK):
        os.makedirs(settings.PATH_STATEMENT_ON_DISK)

    html_path = os.path.join(settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.html")
    with open(html_path, "w", encoding="utf_8") as f:
        f.write("<p>no source here</p>")

    assert get_disk_statement_from_puid(disk_puid, "tex") is None

    resp = otis.get_20x("hint-list", disk_puid)
    # the HTML statement is the page's product, so it stays a content assertion
    otis.assert_has(resp, "<p>no source here</p>")
    # ...but with no .tex alongside it, the source toggle is not offered
    assert resp.context["tex_statement"] is None

    os.remove(html_path)
    if not os.listdir(settings.PATH_STATEMENT_ON_DISK):
        os.rmdir(settings.PATH_STATEMENT_ON_DISK)


@pytest.mark.django_db
def test_problem(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create(puid="SILLY")

    otis.post_20x(
        "arch-index",
        data={"puid": "SILLY", "hyperlink": "https://otis.evanchen.cc/"},
        follow=True,
    )

    problem = Problem.objects.get(puid="SILLY")

    otis.post_20x(
        "problem-update",
        problem.puid,
        data={"hyperlink": "https://aops.com/"},
        follow=True,
    )
    resp = otis.get_20x("problem-update", "SILLY")
    assert resp.context["form"].initial["hyperlink"] == "https://aops.com/"

    problem.refresh_from_db()
    assert problem.hyperlink == "https://aops.com/"


@pytest.mark.django_db
def test_hint(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()

    otis.get_20x("hint-list", problem.puid)
    otis.get_40x("hint-detail", problem.pk, 31)

    otis.get_20x("hint-create", problem.puid)
    otis.post_20x(
        "hint-create",
        problem.puid,
        data={
            "problem": problem.pk,
            "number": 31,
            "keywords": "keywords or something",
            "content": "just solve it",
        },
        follow=True,
    )

    hint: Hint = Hint.objects.get(problem=problem)
    resp = otis.get_20x("hint-detail", problem.puid, 31)
    assert resp.context["hint"] == hint

    otis.get_40x("hint-detail", problem.puid, 41)
    otis.get_20x("hint-detail-pk", hint.pk)
    resp = otis.get_20x("hint-update", problem.puid, 31)
    assert resp.context["form"].initial["keywords"] == hint.keywords
    otis.post_20x(
        "hint-update",
        problem.puid,
        31,
        data={
            "problem": hint.problem_id,
            "number": 41,
            "keywords": hint.keywords,
            "content": hint.content,
            "reason": "Changed number",
        },
        follow=True,
    )

    otis.get_40x("hint-detail", problem.puid, 31)
    otis.get_20x("hint-detail", problem.puid, 41)

    resp = otis.get_20x("hint-update-pk", hint.pk)
    assert resp.context["form"].initial["keywords"] == hint.keywords
    otis.post_20x(
        "hint-update-pk",
        hint.pk,
        data={
            "problem": hint.problem_id,
            "number": 51,
            "keywords": hint.keywords,
            "content": hint.content,
            "reason": "Changed number again",
        },
        follow=True,
    )

    otis.get_40x("hint-detail", problem.puid, 41)
    otis.get_20x("hint-detail", problem.puid, 51)

    otis.post_20x("hint-delete", problem.puid, 51, follow=True)

    assert not Hint.objects.filter(problem=problem).exists()


@pytest.mark.django_db
def test_vote(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()

    otis.get_20x("vote-create", problem.puid)

    resp = otis.post_20x("vote-create", problem.puid, data={"niceness": 4}, follow=True)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])

    assert Vote.objects.get(problem__puid=problem.puid).niceness == 4


@pytest.mark.django_db
def test_lookup(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()

    otis.get_redirects(reverse("arch-index"), "arch-lookup")

    otis.post_redirects(
        problem.get_absolute_url(), "arch-lookup", data={"problem": problem.pk}
    )


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_view_solution(otis):
    problem: Problem = ProblemFactory.create()
    eve = UserFactory.create()
    otis.login(eve)
    resp = otis.get_40x("view-solution", problem.puid)
    assert resp.status_code == 403

    # verified user should instead fail because default storage doesn't
    # have the problem in question
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)
    resp = otis.get_40x("view-solution", problem.puid)
    assert resp.status_code == 404


@pytest.mark.django_db
@override_settings(
    PATH_STATEMENT_ON_DISK=os.path.join(settings.BASE_DIR, "test_static/")
)
def test_view_solution_without_solution_on_bucket(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    disk_puid = "SOLLESS"

    if not os.path.exists(settings.PATH_STATEMENT_ON_DISK):
        os.makedirs(settings.PATH_STATEMENT_ON_DISK)
    html_path = os.path.join(settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.html")
    with open(html_path, "w", encoding="utf_8") as f:
        f.write("<p>statement without solution</p>")

    assert get_disk_statement_from_puid(disk_puid) is not None
    otis.get_not_found("view-solution", disk_puid)

    os.remove(html_path)
    if not os.listdir(settings.PATH_STATEMENT_ON_DISK):
        os.rmdir(settings.PATH_STATEMENT_ON_DISK)


def test_validate_puid():
    with pytest.raises(Http404):
        validate_puid("✈✈✈")
    with pytest.raises(Http404):
        validate_puid("✈" * 1000)
    with pytest.raises(Http404):
        validate_puid("i'm a rock")
    with pytest.raises(Http404):
        validate_puid("A" * 1000)
    validate_puid("15TWNQJ36")
    validate_puid("A" * 24)


@pytest.mark.django_db
def test_disable_hints(otis):
    """Test that disable_hints setting properly hides hints and shows appropriate message."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()
    hint: Hint = HintFactory.create(problem=problem, number=10, keywords="test hint")

    # Test with hints enabled (default) - should see the hint
    resp = otis.get_20x("hint-list", problem.puid)
    assert list(resp.context["hint_list"]) == [hint]
    assert not resp.context["hints_disabled"]

    # Update user profile to disable hints
    profile = UserProfile.objects.get(user=alice)
    profile.disable_hints = True
    profile.save()

    # Test with hints disabled - should see disabled message
    resp = otis.get_20x("hint-list", problem.puid)
    assert resp.context["hints_disabled"]
    assert list(resp.context["hint_list"]) == []
    # the hint's own text must not reach the page either
    otis.assert_not_has(resp, hint.keywords)


@pytest.mark.django_db
def test_no_hints_message(otis):
    """Test that appropriate message is shown when there are genuinely no hints."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()

    # Test with no hints - should see the "no hints yet" message
    resp = otis.get_20x("hint-list", problem.puid)
    assert list(resp.context["hint_list"]) == []
    # genuinely empty is a different state from "you turned hints off"
    assert not resp.context["hints_disabled"]


@pytest.mark.django_db
def test_disable_hints_blocks_detail_view(otis):
    """Test that disable_hints blocks access to individual hint detail pages."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()
    hint: Hint = HintFactory.create(problem=problem, number=15, keywords="blocked hint")

    # First verify the hint is accessible with hints enabled
    otis.get_20x("hint-detail", problem.puid, hint.number)
    otis.get_20x("hint-detail-pk", hint.pk)

    # Disable hints
    profile = UserProfile.objects.get(user=alice)
    profile.disable_hints = True
    profile.save()

    # Now both detail views should return 404
    otis.get_40x("hint-detail", problem.puid, hint.number)
    otis.get_40x("hint-detail-pk", hint.pk)
