import os

import pytest
from django.conf import settings
from django.http import Http404
from django.test import override_settings
from django.urls import reverse

from arch.factories import HintFactory, ProblemFactory
from arch.models import Hint, Problem, Vote, validate_puid
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

    problem_path = os.path.join(settings.PATH_STATEMENT_ON_DISK, f"{disk_puid}.html")

    with open(problem_path, "w", encoding="utf_8") as f:
        f.write("rock and roll")

    otis.get_40x("hint-list", "NONEXISTENT")
    resp = otis.get_20x("hint-list", disk_puid)

    messages = [m.message for m in resp.context["messages"]]
    assert f"Created previously nonexistent problem {disk_puid}" in messages

    otis.assert_has(resp, "rock and roll")

    os.remove(problem_path)
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
    otis.assert_has(otis.get_20x("problem-update", "SILLY"), "https://aops.com/")

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

    otis.assert_has(
        otis.get_20x("hint-create", problem.puid), "Advice for writing hints"
    )
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
    otis.assert_has(resp, hint.content)

    otis.get_40x("hint-detail", problem.puid, 41)
    otis.get_20x("hint-detail-pk", hint.pk)
    otis.assert_has(otis.get_20x("hint-update", problem.puid, 31), hint.keywords)
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

    otis.assert_has(otis.get_20x("hint-update-pk", hint.pk), hint.keywords)
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
    messages = [m.message for m in resp.context["messages"]]
    assert f"You rated {problem.puid} as 4." in messages

    assert Vote.objects.filter(problem__puid=problem.puid).exists()


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
    otis.assert_has(resp, hint.keywords)
    otis.assert_has(resp, "Hint 10")

    # Update user profile to disable hints
    profile = UserProfile.objects.get(user=alice)
    profile.disable_hints = True
    profile.save()

    # Test with hints disabled - should see disabled message
    resp = otis.get_20x("hint-list", problem.puid)
    otis.assert_has(resp, "Hints are disabled in your settings")
    otis.assert_has(resp, "user preferences")
    # Should NOT see the hint
    assert hint.keywords not in resp.content.decode()
    assert "Hint 10" not in resp.content.decode()


@pytest.mark.django_db
def test_no_hints_message(otis):
    """Test that appropriate message is shown when there are genuinely no hints."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(groups=(verified_group,))
    otis.login(alice)

    problem: Problem = ProblemFactory.create()

    # Test with no hints - should see the "no hints yet" message
    resp = otis.get_20x("hint-list", problem.puid)
    otis.assert_has(resp, "There aren't any hints here yet")
    otis.assert_has(resp, "adding a hint")
    # Should NOT see the disabled message
    assert "Hints are disabled" not in resp.content.decode()


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
