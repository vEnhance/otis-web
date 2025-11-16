import datetime
import re

import pytest
from django.core.exceptions import SuspiciousOperation
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from opal.factories import OpalAttemptFactory, OpalHuntFactory, OpalPuzzleFactory
from rpg.factories import AchievementFactory
from rpg.models import AchievementUnlock

from .models import answerize, puzzle_file_name

UTC = datetime.timezone.utc


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
    assert str(OpalHuntFactory.create(name="Your OTIS in April")) == "Your OTIS in April"
    OpalHuntFactory.create().get_absolute_url()
    OpalPuzzleFactory.create().get_absolute_url()
    str(OpalAttemptFactory.create())


@pytest.mark.django_db
def test_puzzle_upload():
    puzzle = OpalPuzzleFactory.create(hunt__slug="hunt", slug="sudoku")
    assert not puzzle.is_uploaded
    with pytest.raises(SuspiciousOperation):
        puzzle_file_name(puzzle, "wrong_file.pdf")
    filename = puzzle_file_name(puzzle, "sudoku.pdf")
    assert re.match(r"opals\/hunt\/[a-z0-9]+\/sudoku.pdf", filename), filename


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
    with freeze_time("2025-09-06"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        assert "will release" in resp.content.decode()
        assert "use your brain" not in resp.content.decode()
    with freeze_time("2025-09-08"):
        resp = otis.get_20x("opal-show-puzzle", puzzle.hunt.slug, puzzle.slug)
        assert "will release" not in resp.content.decode()
        assert "use your brain" in resp.content.decode()
