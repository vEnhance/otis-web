import datetime
import re

from django.core.exceptions import SuspiciousOperation
from freezegun.api import freeze_time

from core.factories import GroupFactory, UserFactory
from evans_django_tools.testsuite import EvanTestCase
from opal.factories import OpalAttemptFactory, OpalHuntFactory, OpalPuzzleFactory
from rpg.factories import AchievementFactory
from rpg.models import AchievementUnlock

from .models import answerize, puzzle_file_name

UTC = datetime.timezone.utc


class TestOPALModels(EvanTestCase):
    def test_answerize(self):
        self.assertEqual(answerize("Third time's the charm"), "THIRDTIMESTHECHARM")
        self.assertEqual(answerize("luminescent"), "LUMINESCENT")
        self.assertEqual(answerize("hindSight IS 20/20 🧐"), "HINDSIGHTIS2020")

    def test_attempt_save_and_log(self):
        puzzle = OpalPuzzleFactory.create(
            hunt__slug="mh21", slug="clueless", answer="Final Proposal"
        )
        attempt1 = OpalAttemptFactory.create(puzzle=puzzle, guess="FINALPROPOSAL")
        self.assertTrue(attempt1.is_correct)
        attempt2 = OpalAttemptFactory.create(puzzle=puzzle, guess="Final Proposal")
        self.assertTrue(attempt2.is_correct)
        attempt3 = OpalAttemptFactory.create(puzzle=puzzle, guess="final proposal 2")
        self.assertFalse(attempt3.is_correct)

        self.assertEqual(puzzle.get_attempt_log_url, r"/opal/guesses/mh21/clueless/")

        admin = UserFactory.create(username="admin", is_superuser=True)
        self.login(admin)
        resp = self.assertGetOK("opal-attempts-list", "mh21", "clueless")
        self.assertEqual(len(resp.context["attempts"]), 3)
        self.assertEqual(resp.context["num_total"], 3)
        self.assertEqual(resp.context["num_correct"], 2)

    def test_unlock_gating(self):
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
            self.assertFalse(hunt.has_started)
            self.assertFalse(puzzle0.can_view(alice))
            self.assertFalse(puzzle1.can_view(alice))
            self.assertFalse(puzzle2.can_view(alice))
            self.assertFalse(puzzle3.can_view(alice))

        with freeze_time("2024-10-01"):
            self.assertTrue(hunt.has_started)

            # Hunt just started
            self.assertFalse(puzzle0.is_solved_by(alice))
            self.assertFalse(puzzle1.is_solved_by(alice))
            self.assertFalse(puzzle2.is_solved_by(alice))
            self.assertFalse(puzzle3.is_solved_by(alice))
            self.assertTrue(puzzle0.can_view(alice))
            self.assertTrue(puzzle1.can_view(alice))
            self.assertFalse(puzzle2.can_view(alice))
            self.assertFalse(puzzle3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 0)

            # Now let's solve puzzle 0 and send some wrong guesses for puzzle 1
            OpalAttemptFactory.create(user=alice, puzzle=puzzle0, guess="0")
            OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="whisky")
            OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="tango")
            OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="foxtrot")
            self.assertTrue(puzzle0.is_solved_by(alice))
            self.assertFalse(puzzle1.is_solved_by(alice))
            self.assertFalse(puzzle2.is_solved_by(alice))
            self.assertFalse(puzzle3.is_solved_by(alice))
            self.assertTrue(puzzle0.can_view(alice))
            self.assertTrue(puzzle1.can_view(alice))
            self.assertFalse(puzzle2.can_view(alice))
            self.assertFalse(puzzle3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 1)

            # Now let's solve puzzle 1
            OpalAttemptFactory.create(user=alice, puzzle=puzzle1, guess="1")
            self.assertTrue(puzzle0.is_solved_by(alice))
            self.assertTrue(puzzle1.is_solved_by(alice))
            self.assertFalse(puzzle2.is_solved_by(alice))
            self.assertFalse(puzzle3.is_solved_by(alice))
            self.assertTrue(puzzle0.can_view(alice))
            self.assertTrue(puzzle1.can_view(alice))
            self.assertTrue(puzzle2.can_view(alice))
            self.assertFalse(puzzle3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 2)

            # Finish puzzle 2
            OpalAttemptFactory.create(user=alice, puzzle=puzzle2, guess="2")
            self.assertTrue(puzzle0.is_solved_by(alice))
            self.assertTrue(puzzle1.is_solved_by(alice))
            self.assertTrue(puzzle2.is_solved_by(alice))
            self.assertFalse(puzzle3.is_solved_by(alice))
            self.assertTrue(puzzle0.can_view(alice))
            self.assertTrue(puzzle1.can_view(alice))
            self.assertTrue(puzzle2.can_view(alice))
            self.assertTrue(puzzle3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 3)

            # But Bob is still at the start
            self.assertFalse(puzzle0.is_solved_by(bob))
            self.assertFalse(puzzle1.is_solved_by(bob))
            self.assertFalse(puzzle2.is_solved_by(bob))
            self.assertFalse(puzzle3.is_solved_by(bob))
            self.assertTrue(puzzle0.can_view(bob))
            self.assertTrue(puzzle1.can_view(bob))
            self.assertFalse(puzzle2.can_view(bob))
            self.assertFalse(puzzle3.can_view(bob))
            self.assertEqual(hunt.num_solves(bob), 0)

    def test_model_methods(self):
        self.assertEqual(str(OpalPuzzleFactory.create(slug="meow")), "meow")
        self.assertEqual(
            str(OpalHuntFactory.create(name="Your OTIS in April")), "Your OTIS in April"
        )
        OpalHuntFactory.create().get_absolute_url()
        OpalPuzzleFactory.create().get_absolute_url()
        str(OpalAttemptFactory.create())

    def test_puzzle_upload(self):
        puzzle = OpalPuzzleFactory.create(hunt__slug="hunt", slug="sudoku")
        self.assertFalse(puzzle.is_uploaded)
        self.assertRaises(
            SuspiciousOperation, puzzle_file_name, puzzle, "wrong_file.pdf"
        )
        filename = puzzle_file_name(puzzle, "sudoku.pdf")
        self.assertTrue(
            re.match(r"opals\/hunt\/[a-z0-9]+\/sudoku.pdf", filename), filename
        )

    def test_author_signups(self):
        hunt = OpalHuntFactory.create(
            author_signup_deadline=None,
            author_signup_url="https://example.org",
        )
        self.assertTrue(hunt.author_signups_are_open)
        hunt.author_signup_url = ""
        hunt.save()
        self.assertFalse(hunt.author_signups_are_open)

        hunt = OpalHuntFactory.create(
            author_signup_deadline=datetime.datetime(2023, 3, 24, tzinfo=UTC),
            author_signup_url="https://example.org",
        )
        with freeze_time("2023-03-01"):
            self.assertTrue(hunt.author_signups_are_open)
        with freeze_time("2023-03-30"):
            self.assertFalse(hunt.author_signups_are_open)

        hunt = OpalHuntFactory.create(
            author_signup_deadline=datetime.datetime(2023, 3, 24, tzinfo=UTC),
            author_signup_url="",
        )
        with freeze_time("2024-03-01"):
            self.assertFalse(hunt.author_signups_are_open)
        with freeze_time("2024-03-30"):
            self.assertFalse(hunt.author_signups_are_open)

    def test_hunt_list(self):
        OpalHuntFactory.create_batch(5)
        alice = UserFactory.create(username="alice")
        self.login(alice)
        resp = self.assertGet20X("opal-hunt-list")
        self.assertEqual(len(resp.context["hunts"]), 5)

    def test_puzzle_list(self):
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
            self.login(alice)
            self.assertGet40X("opal-puzzle-list", "hunt")
            self.login(admin)
            self.assertGet20X("opal-puzzle-list", "hunt")
        with freeze_time("2024-09-25"):
            self.login(alice)
            resp = self.assertGet20X("opal-puzzle-list", "hunt")
            self.assertContains(resp, "Puzzle Unlocked 1")
            self.assertContains(resp, "Puzzle Unlocked 2")
            self.assertContains(resp, "Puzzle Unlocked 3")
            self.assertNotContains(resp, "Puzzle Locked")

    def test_hunt_progress(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(username="alice", groups=(verified_group,))
        bob = UserFactory.create(username="bob", groups=(verified_group,))
        self.login(alice)

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
        self.assertEqual(queryset.count(), 4)
        self.assertTrue(queryset.get(pk=puzzle0.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle1.pk).unlocked)
        self.assertFalse(queryset.get(pk=puzzle2.pk).unlocked)
        self.assertFalse(queryset.get(pk=puzzle3.pk).unlocked)
        self.assertFalse(queryset.get(pk=puzzle0.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle1.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle2.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle3.pk).solved)
        self.assertGet20X("opal-show-puzzle", "hunt", "zero", follow=True)
        self.assertGet20X("opal-show-puzzle", "hunt", "one", follow=True)
        self.assertGet40X("opal-show-puzzle", "hunt", "two", follow=True)
        self.assertGet40X("opal-show-puzzle", "hunt", "three", follow=True)

        # Let's have Alice solve puzzle 0
        resp = self.assertPostOK(
            "opal-show-puzzle",
            "hunt",
            "zero",
            data={"guess": "0"},
            follow=True,
        )
        self.assertContains(resp, "Correct answer")
        self.assertEqual(hunt.num_solves(alice), 1)
        queryset = hunt.get_queryset_for_user(alice)
        self.assertEqual(queryset.count(), 4)
        self.assertTrue(queryset.get(pk=puzzle0.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle1.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle2.pk).unlocked)
        self.assertFalse(queryset.get(pk=puzzle3.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle0.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle1.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle2.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle3.pk).solved)

        # Let's have Alice fail to solve puzzle 1
        for i, guess_word in enumerate(("nani", "da", "heck")):
            resp = self.assertPostOK(
                "opal-show-puzzle",
                "hunt",
                "one",
                data={"guess": guess_word},
                follow=True,
            )
            self.assertContains(resp, "Sorry")
            self.assertFalse(resp.context["solved"])
            self.assertEqual(resp.context["can_attempt"], i < 2)
        resp = self.assertPost40X(
            "opal-show-puzzle",
            "hunt",
            "one",
            data={"guess": "oh no i'm locked out"},
            follow=True,
        )

        # Let's have Alice solve puzzle 2
        resp = self.assertPostOK(
            "opal-show-puzzle",
            "hunt",
            "two",
            data={"guess": "2"},
            follow=True,
        )
        self.assertContains(resp, "Correct answer")
        self.assertEqual(hunt.num_solves(alice), 2)
        queryset = hunt.get_queryset_for_user(alice)
        self.assertEqual(queryset.count(), 4)
        self.assertTrue(queryset.get(pk=puzzle0.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle1.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle2.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle3.pk).unlocked)
        self.assertTrue(queryset.get(pk=puzzle0.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle1.pk).solved)
        self.assertTrue(queryset.get(pk=puzzle2.pk).solved)
        self.assertFalse(queryset.get(pk=puzzle3.pk).solved)

        # But Alice shouldn't be able to submit multiple correct answers
        self.assertPost40X(
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
        self.login(admin)
        self.assertGet20X("opal-show-puzzle", "hunt", "three")

    def test_achievement_unlock(self):
        verified_group = GroupFactory(name="Verified")
        alice = UserFactory.create(username="alice", groups=(verified_group,))
        ach = AchievementFactory.create(diamonds=3)
        self.login(alice)
        puzzle = OpalPuzzleFactory.create(achievement=ach)

        self.assertPost20X(
            "opal-show-puzzle",
            puzzle.hunt.slug,
            puzzle.slug,
            data={"guess": puzzle.answer},
            follow=True,
        )
        self.assertTrue(
            AchievementUnlock.objects.filter(achievement=ach, user=alice).exists()
        )
