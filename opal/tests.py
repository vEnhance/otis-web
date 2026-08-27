import datetime
import re
from unittest import mock

import pytest
from django.contrib.messages import constants as message_levels
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from opal.factories import OpalAttemptFactory, OpalHuntFactory, OpalPuzzleFactory
from opal.views import HUNT_LOG_PAGE_SIZE, RECENT_ATTEMPTS_PER_HUNT, _Eligibility
from rpg.factories import AchievementFactory
from rpg.models import AchievementUnlock

from .models import OpalAttempt, answerize, puzzle_file_name

UTC = datetime.UTC


@pytest.mark.django_db
def test_answerize():
    assert answerize("Third time's the charm") == "THIRDTIMESTHECHARM"
    assert answerize("luminescent") == "LUMINESCENT"
    assert answerize("hindSight IS 20/20 🧐") == "HINDSIGHTIS2020"


@pytest.mark.django_db
def test_attempt_save_and_log(otis):
    puzzle = OpalPuzzleFactory.create(
        hunt__slug="mh21", slug="clueless", answer="Final Proposal"
    )
    attempt1 = OpalAttemptFactory.create(puzzle=puzzle, guess="FINALPROPOSAL")
    assert attempt1.is_correct
    attempt2 = OpalAttemptFactory.create(puzzle=puzzle, guess="Final Proposal")
    assert attempt2.is_correct
    attempt3 = OpalAttemptFactory.create(puzzle=puzzle, guess="final proposal 2")
    assert not attempt3.is_correct

    assert puzzle.get_attempt_log_url == r"/opal/guesses/mh21/clueless/"

    admin = UserFactory.create(username="admin", is_superuser=True)
    otis.login(admin)
    resp = otis.get_20x("opal-attempts-list", "mh21", "clueless")
    assert len(resp.context["attempts"]) == 3
    assert resp.context["num_total"] == 3
    assert resp.context["num_correct"] == 2


@pytest.mark.django_db
def test_unlock_gating():
    alice = UserFactory.create(username="alice")
    bob = UserFactory.create(username="bob")

    # Make some old attempts to verify they don't contribute to the current hunt
    OpalAttemptFactory.create_batch(
        5, user=alice, puzzle__answer="answer", guess="answer"
    )

    # Current hunt
    hunt = OpalHuntFactory.create(
        name="Hunt",
        slug="hunt",
        start_date=datetime.datetime(2024, 9, 1, tzinfo=UTC),
    )
    puzzle0 = OpalPuzzleFactory.create(answer="0", hunt=hunt, num_to_unlock=0)
    puzzle1 = OpalPuzzleFactory.create(answer="1", hunt=hunt, num_to_unlock=0)
    puzzle2 = OpalPuzzleFactory.create(answer="2", hunt=hunt, num_to_unlock=2)
    puzzle3 = OpalPuzzleFactory.create(answer="3", hunt=hunt, num_to_unlock=3)

    with freeze_time("2024-08-01"):
        assert not hunt.has_started
        assert not puzzle0.can_view(alice)
        assert not puzzle1.can_view(alice)
        assert not puzzle2.can_view(alice)
        assert not puzzle3.can_view(alice)

    with freeze_time("2024-10-01"):
        assert hunt.has_started

        # Hunt just started
        assert not puzzle0.is_solved_by(alice)
        assert not puzzle1.is_solved_by(alice)
        assert not puzzle2.is_solved_by(alice)
        assert not puzzle3.is_solved_by(alice)
        assert puzzle0.can_view(alice)
        assert puzzle1.can_view(alice)
        assert not puzzle2.can_view(alice)
        assert not puzzle3.can_view(alice)
        assert hunt.num_solves(alice) == 0

        # Now let's solve puzzle 0 and send some wrong guesses for puzzle 1
        OpalAttemptFactory.create(user=alice, puzzle=puzzle0, guess="0")
        OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="whisky")
        OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="tango")
        OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="foxtrot")
        assert puzzle0.is_solved_by(alice)
        assert not puzzle1.is_solved_by(alice)
        assert not puzzle2.is_solved_by(alice)
        assert not puzzle3.is_solved_by(alice)
        assert puzzle0.can_view(alice)
        assert puzzle1.can_view(alice)
        assert not puzzle2.can_view(alice)
        assert not puzzle3.can_view(alice)
        assert hunt.num_solves(alice) == 1

        # Now let's solve puzzle 1
        OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="1")
        assert puzzle0.is_solved_by(alice)
        assert puzzle1.is_solved_by(alice)
        assert not puzzle2.is_solved_by(alice)
        assert not puzzle3.is_solved_by(alice)
        assert puzzle0.can_view(alice)
        assert puzzle1.can_view(alice)
        assert puzzle2.can_view(alice)
        assert not puzzle3.can_view(alice)
        assert hunt.num_solves(alice) == 2

        # Finish puzzle 2
        OpalAttemptFactory.create(user=alice, puzzle=puzzle2, guess="2")
        assert puzzle0.is_solved_by(alice)
        assert puzzle1.is_solved_by(alice)
        assert puzzle2.is_solved_by(alice)
        assert not puzzle3.is_solved_by(alice)
        assert puzzle0.can_view(alice)
        assert puzzle1.can_view(alice)
        assert puzzle2.can_view(alice)
        assert puzzle3.can_view(alice)
        assert hunt.num_solves(alice) == 3

        # But Bob is still at the start
        assert not puzzle0.is_solved_by(bob)
        assert not puzzle1.is_solved_by(bob)
        assert not puzzle2.is_solved_by(bob)
        assert not puzzle3.is_solved_by(bob)
        assert puzzle0.can_view(bob)
        assert puzzle1.can_view(bob)
        assert not puzzle2.can_view(bob)
        assert not puzzle3.can_view(bob)
        assert hunt.num_solves(bob) == 0


@pytest.mark.django_db
def test_model_methods():
    assert str(OpalPuzzleFactory.create(slug="meow")) == "meow"
    assert (
        str(OpalHuntFactory.create(name="Your OTIS in April")) == "Your OTIS in April"
    )
    OpalHuntFactory.create().get_absolute_url()
    OpalPuzzleFactory.create().get_absolute_url()
    str(OpalAttemptFactory.create())


@pytest.mark.django_db
def test_puzzle_upload():
    puzzle = OpalPuzzleFactory.create(hunt__slug="hunt", slug="sudoku")
    assert not puzzle.is_uploaded
    for name in ("sudoku.pdf", "differently_named_file.pdf"):
        filename = puzzle_file_name(puzzle, name)
        assert re.match(rf"opals\/hunt\/[a-z0-9]+\/{name}", filename), filename


@pytest.mark.django_db
def test_puzzle_admin_upload_slug_mismatch(otis, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    puzzle = OpalPuzzleFactory.create(hunt__slug="hunt", slug="sudoku")
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    form_data = {
        "hunt": puzzle.hunt.pk,
        "title": puzzle.title,
        "slug": puzzle.slug,
        "answer": puzzle.answer,
        "partial_answers": "",
        "order": puzzle.order,
        "num_to_unlock": puzzle.num_to_unlock,
        "credits": "",
        "guess_limit": puzzle.guess_limit,
        "errata": "",
        "hint_text": "",
    }
    resp = otis.post(
        "admin:opal_opalpuzzle_change",
        puzzle.pk,
        data=form_data
        | {
            "content": SimpleUploadedFile(
                "differently_named_file.pdf", b"%PDF-1.4 sudoku"
            )
        },
        follow=True,
    )
    # the admin warns but saves anyway; the sentence names both file and slug
    assert any(m.level == message_levels.WARNING for m in resp.context["messages"])
    puzzle.refresh_from_db()
    assert puzzle.content.name.endswith("differently_named_file.pdf")

    resp = otis.post(
        "admin:opal_opalpuzzle_change",
        puzzle.pk,
        data=form_data
        | {"content": SimpleUploadedFile("sudoku.pdf", b"%PDF-1.4 sudoku")},
        follow=True,
    )
    # a correctly named file draws no warning
    assert not any(m.level == message_levels.WARNING for m in resp.context["messages"])
    puzzle.refresh_from_db()
    assert puzzle.content.name.endswith("sudoku.pdf")


@pytest.mark.django_db
def test_author_signups():
    hunt = OpalHuntFactory.create(
        author_signup_deadline=None,
        author_signup_url="https://example.org",
    )
    assert hunt.author_signups_are_open
    hunt.author_signup_url = ""
    hunt.save()
    assert not hunt.author_signups_are_open

    hunt = OpalHuntFactory.create(
        author_signup_deadline=datetime.datetime(2023, 3, 24, tzinfo=UTC),
        author_signup_url="https://example.org",
    )
    with freeze_time("2023-03-01"):
        assert hunt.author_signups_are_open
    with freeze_time("2023-03-30"):
        assert not hunt.author_signups_are_open

    hunt = OpalHuntFactory.create(
        author_signup_deadline=datetime.datetime(2023, 3, 24, tzinfo=UTC),
        author_signup_url="",
    )
    with freeze_time("2024-03-01"):
        assert not hunt.author_signups_are_open
    with freeze_time("2024-03-30"):
        assert not hunt.author_signups_are_open


@pytest.mark.django_db
def test_hunt_list(otis):
    OpalHuntFactory.create_batch(5)
    alice = UserFactory.create(username="alice")
    otis.login(alice)
    resp = otis.get_20x("opal-hunt-list")
    assert len(resp.context["hunts"]) == 5


@pytest.mark.django_db
def test_artwork_urls():
    hunt = OpalHuntFactory.create(artwork_slug="opal3")
    assert hunt.has_artwork
    assert hunt.artwork_url == "https://gallery.evanchen.cc/webp/opal3.webp"
    assert (
        hunt.artwork_thumb_md_url == "https://gallery.evanchen.cc/thumb-md/opal3.webp"
    )
    assert (
        hunt.artwork_thumb_sm_url == "https://gallery.evanchen.cc/thumb-sm/opal3.webp"
    )

    blank = OpalHuntFactory.create(artwork_slug="")
    assert not blank.has_artwork
    assert blank.artwork_url is None
    assert blank.artwork_thumb_md_url is None
    assert blank.artwork_thumb_sm_url is None


@pytest.mark.django_db
def test_artwork_display(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)

    hunt = OpalHuntFactory.create(slug="withart", artwork_slug="opal3")
    OpalPuzzleFactory.create(hunt=hunt, slug="puzzle", num_to_unlock=0)
    blank_hunt = OpalHuntFactory.create(slug="noart", artwork_slug="")
    OpalPuzzleFactory.create(hunt=blank_hunt, slug="other", num_to_unlock=0)

    # one hunt has artwork and the other gets a placeholder of the same size
    resp = otis.get_20x("opal-hunt-list")
    otis.assert_testid(resp, "opal-artwork", count=1)
    otis.assert_testid(resp, "opal-artwork-blank", count=1)
    # the thumbnail links to the full-resolution image on the CDN
    otis.assert_has(resp, "https://gallery.evanchen.cc/webp/opal3.webp")

    resp = otis.get_20x("opal-puzzle-list", "withart")
    otis.assert_testid(resp, "opal-artwork", count=1)
    otis.assert_no_testid(resp, "opal-artwork-blank")
    resp = otis.get_20x("opal-puzzle-list", "noart")
    otis.assert_testid(resp, "opal-artwork-blank", count=1)
    otis.assert_no_testid(resp, "opal-artwork")

    resp = otis.get_20x("opal-show-puzzle", "withart", "puzzle")
    otis.assert_testid(resp, "opal-artwork", count=1)
    resp = otis.get_20x("opal-show-puzzle", "noart", "other")
    otis.assert_testid(resp, "opal-artwork-blank", count=1)

    otis.login(UserFactory.create(username="root", is_staff=True, is_superuser=True))
    resp = otis.get_20x("opal-leaderboard", "withart")
    otis.assert_testid(resp, "opal-artwork", count=1)
    resp = otis.get_20x("opal-leaderboard", "noart")
    otis.assert_testid(resp, "opal-artwork-blank", count=1)

    # the finish page shows the hunt artwork in place of the achievement image
    otis.login(alice)
    solved = OpalPuzzleFactory.create(
        hunt=hunt, slug="solved", achievement=AchievementFactory.create()
    )
    OpalAttemptFactory.create(user=alice, puzzle=solved, guess=solved.answer)
    resp = otis.get_20x("opal-finish", "withart", "solved")
    otis.assert_testid(resp, "opal-artwork", count=1)


@pytest.mark.django_db
def test_puzzle_list(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(
        username="root", is_superuser=True, groups=(verified_group,)
    )

    hunt = OpalHuntFactory.create(
        slug="hunt", start_date=datetime.datetime(2024, 8, 30, tzinfo=UTC)
    )
    OpalPuzzleFactory.create(title="Puzzle Unlocked 1", hunt=hunt, num_to_unlock=0)
    OpalPuzzleFactory.create(title="Puzzle Unlocked 2", hunt=hunt, num_to_unlock=0)
    OpalPuzzleFactory.create(title="Puzzle Unlocked 3", hunt=hunt, num_to_unlock=0)
    OpalPuzzleFactory.create(title="Puzzle Locked", hunt=hunt, num_to_unlock=1)
    OpalPuzzleFactory.create(title="Puzzle Locked", hunt=hunt, num_to_unlock=2)

    with freeze_time("2024-08-25"):
        otis.login(alice)
        otis.get_40x("opal-puzzle-list", "hunt")
        otis.login(admin)
        otis.get_20x("opal-puzzle-list", "hunt")
    with freeze_time("2024-09-25"):
        otis.login(alice)
        resp = otis.get_20x("opal-puzzle-list", "hunt")
        assert "Puzzle Unlocked 1" in resp.content.decode()
        assert "Puzzle Unlocked 2" in resp.content.decode()
        assert "Puzzle Unlocked 3" in resp.content.decode()
        assert "Puzzle Locked" not in resp.content.decode()


@pytest.mark.django_db
def test_hunt_progress(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    bob = UserFactory.create(username="bob", groups=(verified_group,))
    otis.login(alice)

    # Make some old attempts to verify they don't contribute to the current hunt
    OpalAttemptFactory.create_batch(15, user=alice, is_correct=False)
    OpalAttemptFactory.create_batch(3, user=alice, is_correct=False)

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle0 = OpalPuzzleFactory.create(
        slug="zero", answer="0", hunt=hunt, num_to_unlock=0, guess_limit=3
    )
    puzzle1 = OpalPuzzleFactory.create(
        slug="one", answer="1", hunt=hunt, num_to_unlock=0, guess_limit=3
    )
    puzzle2 = OpalPuzzleFactory.create(
        slug="two", answer="2", hunt=hunt, num_to_unlock=1, guess_limit=3
    )
    puzzle3 = OpalPuzzleFactory.create(
        slug="three", answer="3", hunt=hunt, num_to_unlock=2, guess_limit=3
    )

    # Make sure Bob's attempts don't do anything
    OpalAttemptFactory.create(user=bob, puzzle=puzzle0, guess="0")
    OpalAttemptFactory.create(user=bob, puzzle=puzzle1, guess="1")
    OpalAttemptFactory.create(user=bob, puzzle=puzzle2, guess="2")
    OpalAttemptFactory.create(user=bob, puzzle=puzzle3, guess="3")

    queryset = hunt.get_queryset_for_user(alice)
    assert queryset.count() == 4
    assert queryset.get(pk=puzzle0.pk).unlocked
    assert queryset.get(pk=puzzle1.pk).unlocked
    assert not queryset.get(pk=puzzle2.pk).unlocked
    assert not queryset.get(pk=puzzle3.pk).unlocked
    assert not queryset.get(pk=puzzle0.pk).solved
    assert not queryset.get(pk=puzzle1.pk).solved
    assert not queryset.get(pk=puzzle2.pk).solved
    assert not queryset.get(pk=puzzle3.pk).solved
    otis.get_20x("opal-show-puzzle", "hunt", "zero", follow=True)
    otis.get_20x("opal-show-puzzle", "hunt", "one", follow=True)
    otis.get_40x("opal-show-puzzle", "hunt", "two")
    otis.get_40x("opal-show-puzzle", "hunt", "three")

    # Let's have Alice solve puzzle 0
    resp = otis.post_20x(
        "opal-show-puzzle",
        "hunt",
        "zero",
        data={"guess": "0"},
        follow=True,
    )
    assert "Correct answer" in resp.content.decode()
    assert hunt.num_solves(alice) == 1
    queryset = hunt.get_queryset_for_user(alice)
    assert queryset.count() == 4
    assert queryset.get(pk=puzzle0.pk).unlocked
    assert queryset.get(pk=puzzle1.pk).unlocked
    assert queryset.get(pk=puzzle2.pk).unlocked
    assert not queryset.get(pk=puzzle3.pk).unlocked
    assert queryset.get(pk=puzzle0.pk).solved
    assert not queryset.get(pk=puzzle1.pk).solved
    assert not queryset.get(pk=puzzle2.pk).solved
    assert not queryset.get(pk=puzzle3.pk).solved

    # Let's have Alice fail to solve puzzle 1
    for i, guess_word in enumerate(("nani", "da", "heck")):
        resp = otis.post_20x(
            "opal-show-puzzle",
            "hunt",
            "one",
            data={"guess": guess_word},
            follow=True,
        )
        assert "Sorry" in resp.content.decode()
        assert not resp.context["solved"]
        assert resp.context["can_attempt"] == (i < 2)
    otis.post_40x(
        "opal-show-puzzle",
        "hunt",
        "one",
        data={"guess": "oh no i'm locked out"},
        follow=True,
    )

    # Let's have Alice solve puzzle 2
    resp = otis.post_20x(
        "opal-show-puzzle",
        "hunt",
        "two",
        data={"guess": "2"},
        follow=True,
    )
    assert "Correct answer" in resp.content.decode()
    assert hunt.num_solves(alice) == 2
    queryset = hunt.get_queryset_for_user(alice)
    assert queryset.count() == 4
    assert queryset.get(pk=puzzle0.pk).unlocked
    assert queryset.get(pk=puzzle1.pk).unlocked
    assert queryset.get(pk=puzzle2.pk).unlocked
    assert queryset.get(pk=puzzle3.pk).unlocked
    assert queryset.get(pk=puzzle0.pk).solved
    assert not queryset.get(pk=puzzle1.pk).solved
    assert queryset.get(pk=puzzle2.pk).solved
    assert not queryset.get(pk=puzzle3.pk).solved

    # But Alice shouldn't be able to submit multiple correct answers
    otis.post_40x(
        "opal-show-puzzle",
        "hunt",
        "two",
        data={"guess": "two"},
        follow=True,
    )

    # Meanwhile, admins should be omniscient
    admin = UserFactory.create(
        username="root", is_superuser=True, groups=(verified_group,)
    )
    otis.login(admin)
    otis.get_20x("opal-show-puzzle", "hunt", "three")


@pytest.mark.django_db
def test_achievement_unlock(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    ach = AchievementFactory.create(diamonds=3)
    otis.login(alice)
    puzzle = OpalPuzzleFactory.create(achievement=ach)

    otis.post_20x(
        "opal-show-puzzle",
        puzzle.hunt.slug,
        puzzle.slug,
        data={"guess": puzzle.answer},
        follow=True,
    )
    assert AchievementUnlock.objects.filter(achievement=ach, user=alice).exists()


@pytest.mark.django_db
def test_hint_visibility(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)
    puzzle = OpalPuzzleFactory.create(
        slug="puzzle",
        hunt__start_date=datetime.datetime(2025, 9, 5, tzinfo=UTC),
        hunt__hints_released_date=datetime.datetime(2025, 9, 7, tzinfo=UTC),
        hint_text="To solve the puzzle, use your brain.",
        hint_text_rendered="<p>To solve the puzzle, use your brain.</p>",
    )
    with freeze_time("2025-09-04"):
        otis.get_40x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
    # before the release date the hint text must not leak into the page
    with freeze_time("2025-09-06"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        assert resp.context["show_hints"] is False
        otis.assert_not_has(resp, "use your brain")
    with freeze_time("2025-09-08"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        assert resp.context["show_hints"] is True
        otis.assert_has(resp, "use your brain")


@pytest.mark.django_db
def test_hint_visibility_without_hint_text(otis):
    """A puzzle with no pre-written hints says so once hints are released."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)
    puzzle = OpalPuzzleFactory.create(
        slug="puzzle",
        hunt__start_date=datetime.datetime(2025, 9, 5, tzinfo=UTC),
        hunt__hints_released_date=datetime.datetime(2025, 9, 7, tzinfo=UTC),
    )
    assert not puzzle.hint_text_rendered
    with freeze_time("2025-09-06"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        otis.assert_testid(resp, "opal-hints-pending")
    with freeze_time("2025-09-08"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        assert resp.context["show_hints"] is True
        otis.assert_testid(resp, "opal-hints-none")
        otis.assert_no_testid(resp, "opal-hints-available")


@pytest.mark.django_db
def test_leaderboard(otis):
    """Test the leaderboard view (admin only)."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(
        username="alice",
        first_name="Alice",
        last_name="Aardvark",
        groups=(verified_group,),
    )
    bob = UserFactory.create(
        username="bob", first_name="Bob", last_name="Beta", groups=(verified_group,)
    )
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    hunt = OpalHuntFactory.create(
        slug="hunt",
        start_date=datetime.datetime(2024, 8, 1, tzinfo=UTC),
    )
    puzzle1 = OpalPuzzleFactory.create(
        hunt=hunt, answer="one", order=1, is_metapuzzle=False
    )
    puzzle2 = OpalPuzzleFactory.create(
        hunt=hunt, answer="two", order=2, is_metapuzzle=False
    )
    puzzle3 = OpalPuzzleFactory.create(
        hunt=hunt, answer="three", order=3, is_metapuzzle=True
    )

    # Alice solves all puzzles (including meta) after hunt start
    with freeze_time("2024-08-15"):
        OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="one")
        OpalAttemptFactory.create(user=alice, puzzle=puzzle2, guess="two")
        OpalAttemptFactory.create(user=alice, puzzle=puzzle3, guess="three")

    # Bob solves first puzzle only
    with freeze_time("2024-08-20"):
        OpalAttemptFactory.create(user=bob, puzzle=puzzle1, guess="one")

    # Test access control
    otis.login(alice)
    otis.get_40x("opal-leaderboard", "hunt")

    otis.login(admin)
    resp = otis.get_20x("opal-leaderboard", "hunt")
    assert resp.context["hunt"] == hunt
    assert {row["name"] for row in resp.context["rows"]} == {
        "Alice Aardvark",
        "Bob Beta",
    }


@pytest.mark.django_db
def test_leaderboard_early_access(otis):
    """Test the leaderboard with early access users (testsolvers)."""
    testsolver_group = GroupFactory(name="Testsolver")
    testsolver = UserFactory.create(
        username="testsolver",
        first_name="Test",
        last_name="Solver",
        groups=(testsolver_group,),
    )
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    hunt = OpalHuntFactory.create(
        slug="hunt",
        start_date=datetime.datetime(2024, 8, 10, tzinfo=UTC),
    )
    puzzle1 = OpalPuzzleFactory.create(hunt=hunt, answer="one", order=1)

    # Testsolver solves before hunt starts (early access)
    with freeze_time("2024-08-05"):
        OpalAttemptFactory.create(user=testsolver, puzzle=puzzle1, guess="one")

    otis.login(admin)
    resp = otis.get_20x("opal-leaderboard", "hunt")
    rows = resp.context["rows"]
    assert len(rows) == 1
    assert rows[0]["has_early_access"] is True


@pytest.mark.django_db
def test_person_log(otis):
    """Test the person_log view (admin only)."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(hunt=hunt, answer="answer")

    # Alice makes some attempts
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="wrong1")
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="wrong2")
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="answer")

    # Test access control
    otis.login(alice)
    otis.get_40x("opal-person-log", "hunt", alice.pk)

    otis.login(admin)
    resp = otis.get_20x("opal-person-log", "hunt", alice.pk)
    assert resp.context["hunt"] == hunt
    assert resp.context["hunter"] == alice
    assert len(resp.context["attempts"]) == 3


@pytest.mark.django_db
def test_finish_page(otis):
    """Test the finish page (after solving a puzzle with achievement)."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))

    ach = AchievementFactory.create(diamonds=5)
    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(
        hunt=hunt, slug="final", answer="answer", achievement=ach
    )

    otis.login(alice)

    # Cannot access finish page without solving
    otis.get_40x("opal-finish", "hunt", "final")

    # Solve the puzzle
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="answer")

    # Now can access finish page
    resp = otis.get_20x("opal-finish", "hunt", "final")
    assert resp.context["puzzle"] == puzzle
    assert resp.context["achievement"] == ach


@pytest.mark.django_db
def test_finish_page_no_achievement(otis):
    """Test finish page for puzzle without achievement - should be forbidden."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(
        hunt=hunt, slug="noach", answer="answer", achievement=None
    )

    otis.login(alice)
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="answer")

    # Should be forbidden since puzzle has no achievement
    otis.get_40x("opal-finish", "hunt", "noach")


@pytest.mark.django_db
def test_close_answer(otis):
    """Test submitting a close answer."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))

    hunt = OpalHuntFactory.create(slug="hunt")
    OpalPuzzleFactory.create(
        hunt=hunt,
        slug="puzzle",
        answer="CORRECT",
        partial_answers="CORRELATION\nALMOSTCORRECT",
    )

    otis.login(alice)
    resp = otis.post_20x(
        "opal-show-puzzle",
        "hunt",
        "puzzle",
        data={"guess": "CORRELATION"},
        follow=True,
    )
    # a correct-but-not-final guess is acknowledged without solving the puzzle
    assert any(m.level == message_levels.WARNING for m in resp.context["messages"])


@pytest.mark.django_db
def test_guess_budget_is_rechecked_under_the_lock(otis):
    """A guess that stops being eligible while it waits for the lock is refused.

    The first `_eligibility` is the optimistic check that decides whether to show
    the form; the second runs holding the puzzle row. A guess submitted in
    parallel that used up the last of the budget in between shows up here as the
    two disagreeing, and the later guess must not be evaluated.
    """
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(
        slug="one", answer="1", hunt=hunt, num_to_unlock=0, guess_limit=3
    )

    with mock.patch(
        "opal.views._eligibility",
        side_effect=[
            _Eligibility(False, OpalAttempt.objects.none(), True),
            _Eligibility(False, OpalAttempt.objects.none(), False),
        ],
    ):
        otis.post_40x(
            "opal-show-puzzle", "hunt", "one", data={"guess": "1"}, follow=True
        )

    assert not OpalAttempt.objects.filter(puzzle=puzzle, user=alice).exists()


@pytest.mark.django_db
def test_recent_activity(otis):
    """The all-hunts activity page shows the newest guesses of every hunt."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    old_hunt = OpalHuntFactory.create(
        slug="old", start_date=datetime.datetime(2024, 1, 1, tzinfo=UTC)
    )
    new_hunt = OpalHuntFactory.create(
        slug="new", start_date=datetime.datetime(2025, 1, 1, tzinfo=UTC)
    )
    OpalHuntFactory.create(
        slug="quiet", start_date=datetime.datetime(2023, 1, 1, tzinfo=UTC)
    )
    old_puzzle = OpalPuzzleFactory.create(hunt=old_hunt, answer="old")
    new_puzzle = OpalPuzzleFactory.create(hunt=new_hunt, answer="new")

    OpalAttemptFactory.create(user=alice, puzzle=old_puzzle, guess="nope")
    fresh = [
        OpalAttemptFactory.create(user=alice, puzzle=new_puzzle, guess=f"guess{i}")
        for i in range(RECENT_ATTEMPTS_PER_HUNT + 5)
    ]

    otis.login(alice)
    otis.get_40x("opal-recent-activity")

    otis.login(admin)
    resp = otis.get_20x("opal-recent-activity")
    sections = resp.context["sections"]
    # a section for every hunt, newest hunt first, even the one nobody guessed on
    assert [section["hunt"].slug for section in sections] == ["new", "old", "quiet"]
    # each hunt is capped at its most recent guesses, newest first
    assert [attempt.pk for attempt in sections[0]["attempts"]] == [
        attempt.pk for attempt in reversed(fresh[-RECENT_ATTEMPTS_PER_HUNT:])
    ]
    assert len(sections[1]["attempts"]) == 1
    assert sections[2]["attempts"] == []


@pytest.mark.django_db
def test_recent_activity_solve_counts(otis):
    """The solve count on a row counts only that hunt, and only correct guesses."""
    alice = UserFactory.create(username="alice")
    bob = UserFactory.create(username="bob")
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle1 = OpalPuzzleFactory.create(hunt=hunt, answer="one")
    puzzle2 = OpalPuzzleFactory.create(hunt=hunt, answer="two")
    other_puzzle = OpalPuzzleFactory.create(answer="elsewhere")

    OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="one")
    OpalAttemptFactory.create(user=alice, puzzle=puzzle2, guess="two")
    OpalAttemptFactory.create(user=alice, puzzle=other_puzzle, guess="elsewhere")
    bobs_guess = OpalAttemptFactory.create(user=bob, puzzle=puzzle1, guess="wrong")

    otis.login(admin)
    for resp in (
        otis.get_20x("opal-recent-activity"),
        otis.get_20x("opal-hunt-log", "hunt"),
    ):
        if "sections" in resp.context:
            rows = next(
                s["attempts"] for s in resp.context["sections"] if s["hunt"] == hunt
            )
        else:
            rows = resp.context["attempts"]
        solve_counts = {attempt.pk: attempt.solve_count for attempt in rows}
        # Alice's solve elsewhere doesn't count, and Bob has solved nothing here
        assert solve_counts.pop(bobs_guess.pk) == 0
        assert set(solve_counts.values()) == {2}


@pytest.mark.django_db
def test_guess_log_row_styling(otis):
    """Every guess log marks testsolvers and finishers the way the leaderboard does."""
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)
    tess = UserFactory.create(username="tess", first_name="Tess", last_name="Solver")
    alice = UserFactory.create(username="alice", first_name="Alice", last_name="A")
    bob = UserFactory.create(username="bob", first_name="Bob", last_name="B")

    hunt = OpalHuntFactory.create(
        slug="hunt", start_date=datetime.datetime(2024, 8, 10, tzinfo=UTC)
    )
    feeder = OpalPuzzleFactory.create(
        hunt=hunt, slug="feeder", answer="one", order=1, is_metapuzzle=False
    )
    meta = OpalPuzzleFactory.create(
        hunt=hunt, slug="meta", answer="two", order=2, is_metapuzzle=True
    )

    # Tess testsolves the whole hunt before it opens; Alice finishes it after.
    with freeze_time("2024-08-05"):
        tess_feeder = OpalAttemptFactory.create(user=tess, puzzle=feeder, guess="one")
        tess_meta = OpalAttemptFactory.create(user=tess, puzzle=meta, guess="two")
    with freeze_time("2024-08-15"):
        alice_feeder = OpalAttemptFactory.create(user=alice, puzzle=feeder, guess="one")
        alice_meta = OpalAttemptFactory.create(user=alice, puzzle=meta, guess="two")
        # Bob misses the feeder, then gets it, then never does get the meta
        bob_miss = OpalAttemptFactory.create(user=bob, puzzle=feeder, guess="nope")
        bob_feeder = OpalAttemptFactory.create(user=bob, puzzle=feeder, guess="one")
        bob_stuck = OpalAttemptFactory.create(user=bob, puzzle=meta, guess="nope")

    expected = {
        # a testsolver's check is grayed out, and their meta is 🆗
        tess_feeder.pk: ("☑️", "table-primary"),
        tess_meta.pk: ("🆗", "table-primary"),
        # someone who finished the hunt for real gets ✅, 🈴, and a green row
        alice_feeder.pk: ("✅", "table-success"),
        alice_meta.pk: ("🈴", "table-success"),
        # Bob is still hunting: the puzzle he did eventually get is untinted,
        # a miss on it included, but the one he never got goes yellow
        bob_miss.pk: ("✖️", ""),
        bob_feeder.pk: ("✅", ""),
        bob_stuck.pk: ("✖️", "table-warning"),
    }

    def styling(attempts) -> dict[int, tuple[str, str]]:
        return {a.pk: (a.emoji, a.row_class) for a in attempts}

    otis.login(admin)

    # the per-hunt log and the all-hunt activity page see every guess
    resp = otis.get_20x("opal-hunt-log", "hunt")
    assert styling(resp.context["attempts"]) == expected

    resp = otis.get_20x("opal-recent-activity")
    section = next(s for s in resp.context["sections"] if s["hunt"] == hunt)
    assert styling(section["attempts"]) == expected

    # the per-puzzle log sees one puzzle's guesses
    resp = otis.get_20x("opal-attempts-list", "hunt", "meta")
    assert styling(resp.context["attempts"]) == {
        pk: expected[pk] for pk in (tess_meta.pk, alice_meta.pk, bob_stuck.pk)
    }

    # the per-user log sees one person's guesses, and a testsolver's stay blue
    resp = otis.get_20x("opal-person-log", "hunt", tess.pk)
    assert styling(resp.context["attempts"]) == {
        pk: expected[pk] for pk in (tess_feeder.pk, tess_meta.pk)
    }
    resp = otis.get_20x("opal-person-log", "hunt", bob.pk)
    assert styling(resp.context["attempts"]) == {
        pk: expected[pk] for pk in (bob_miss.pk, bob_feeder.pk, bob_stuck.pk)
    }

    # once Bob finishes, the hunt-wide green wins over the per-puzzle yellow
    OpalAttemptFactory.create(user=bob, puzzle=meta, guess="two")
    resp = otis.get_20x("opal-person-log", "hunt", bob.pk)
    assert {a.pk: a.row_class for a in resp.context["attempts"]} == {
        a.pk: "table-success" for a in resp.context["attempts"]
    }

    # and the leaderboard the logs are mirroring agrees on both counts
    resp = otis.get_20x("opal-leaderboard", "hunt")
    rows = {row["name"]: row for row in resp.context["rows"]}
    assert rows["Tess Solver"]["emoji_string"] == "☑️🆗"
    assert rows["Tess Solver"]["row_class"] == "table-primary"
    assert rows["Alice A"]["emoji_string"] == "✅🈴"
    assert rows["Alice A"]["row_class"] == "table-success"


@pytest.mark.django_db
def test_guess_log_query_count(otis):
    """A guess log costs the same number of queries however many rows it has."""
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)
    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(hunt=hunt, slug="puzzle", answer="answer")
    alice = UserFactory.create(username="alice")
    OpalAttemptFactory.create(user=alice, puzzle=puzzle, guess="answer")

    otis.login(admin)
    views = (
        ("opal-hunt-log", ("hunt",)),
        ("opal-recent-activity", ()),
        ("opal-attempts-list", ("hunt", "puzzle")),
        ("opal-person-log", ("hunt", alice.pk)),
    )

    def query_count(name: str, args: tuple) -> int:
        # The first hit of a view in a test process pays one-off costs (the
        # session row, the template loader), so warm it up before counting.
        otis.get_20x(name, *args)
        with CaptureQueriesContext(connection) as captured:
            otis.get_20x(name, *args)
        return len(captured)

    baseline = {name: query_count(name, args) for name, args in views}

    # a page an order of magnitude longer, with more guessers on it
    for i in range(20):
        user = UserFactory.create(username=f"guesser{i}")
        OpalAttemptFactory.create_batch(2, user=user, puzzle=puzzle, guess="nope")
    OpalAttemptFactory.create_batch(20, user=alice, puzzle=puzzle, guess="nope")

    assert {name: query_count(name, args) for name, args in views} == baseline


@pytest.mark.django_db
def test_hunt_log(otis):
    """The per-hunt guess log paginates every guess, newest first."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    hunt = OpalHuntFactory.create(slug="hunt")
    puzzle = OpalPuzzleFactory.create(hunt=hunt, answer="answer")
    other_puzzle = OpalPuzzleFactory.create(answer="answer")

    # Frozen time makes every guess share a timestamp, which is exactly the case
    # the pk tiebreaker in the ordering exists for.
    with freeze_time("2025-03-04"):
        attempts = OpalAttemptFactory.create_batch(
            HUNT_LOG_PAGE_SIZE + 3, user=alice, puzzle=puzzle, guess="wrong"
        )
    OpalAttemptFactory.create(user=alice, puzzle=other_puzzle, guess="wrong")

    otis.login(alice)
    otis.get_40x("opal-hunt-log", "hunt")

    otis.login(admin)
    resp = otis.get_20x("opal-hunt-log", "hunt")
    assert resp.context["hunt"] == hunt
    # guesses on other hunts stay out of this log
    assert resp.context["paginator"].count == len(attempts)
    assert resp.context["page_obj"].paginator.num_pages == 2
    newest_first = [attempt.pk for attempt in reversed(attempts)]
    assert [a.pk for a in resp.context["attempts"]] == newest_first[:HUNT_LOG_PAGE_SIZE]
    otis.assert_testid(resp, "opal-attempt-row", count=HUNT_LOG_PAGE_SIZE)

    resp = otis.get_20x("opal-hunt-log", "hunt", data={"page": 2})
    assert [a.pk for a in resp.context["attempts"]] == newest_first[HUNT_LOG_PAGE_SIZE:]

    otis.get_not_found("opal-hunt-log", "nonexistent")


@pytest.mark.django_db
def test_staff_log_links_on_hunt_list(otis):
    """Only admins see the links to the guess logs from the hunt list."""
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    admin = UserFactory.create(username="admin", is_staff=True, is_superuser=True)

    OpalHuntFactory.create(
        slug="started", start_date=datetime.datetime(2024, 1, 1, tzinfo=UTC)
    )
    OpalHuntFactory.create(
        slug="upcoming", start_date=datetime.datetime(2099, 1, 1, tzinfo=UTC)
    )
    OpalHuntFactory.create(slug="archived", active=False)

    otis.login(alice)
    resp = otis.get_20x("opal-hunt-list")
    otis.assert_no_testid(resp, "opal-recent-activity-link")
    otis.assert_no_testid(resp, "opal-hunt-log-link")

    otis.login(admin)
    resp = otis.get_20x("opal-hunt-list")
    otis.assert_testid(resp, "opal-hunt-log-link", count=3)
