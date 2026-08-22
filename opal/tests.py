import datetime
import re
from unittest import mock

import pytest
from django.contrib.messages import constants as message_levels
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from opal.factories import OpalAttemptFactory, OpalHuntFactory, OpalPuzzleFactory
from opal.views import _Eligibility
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
