import datetime

from freezegun.api import freeze_time

from core.factories import UserFactory
from evans_django_tools.testsuite import EvanTestCase
from opal.factories import OpalAttemptFactory, OpalHuntFactory, OpalPuzzleFactory

from .models import answerize

UTC = datetime.timezone.utc


class TestOPALModels(EvanTestCase):
    def test_answerize(self):
        self.assertEqual(answerize("Third time's the charm"), "THIRDTIMESTHECHARM")
        self.assertEqual(answerize("luminescent"), "LUMINESCENT")
        self.assertEqual(answerize("hindSight IS 20/20 🧐"), "HINDSIGHTIS2020")

    def test_attempt_save(self):
        puzzle = OpalPuzzleFactory(answer="Final Proposal")
        attempt1 = OpalAttemptFactory.create(puzzle=puzzle, guess="FINALPROPOSAL")
        self.assertTrue(attempt1.is_correct)
        attempt2 = OpalAttemptFactory.create(puzzle=puzzle, guess="Final Proposal")
        self.assertTrue(attempt2.is_correct)
        attempt3 = OpalAttemptFactory.create(puzzle=puzzle, guess="final proposal 2")
        self.assertFalse(attempt3.is_correct)

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
        puzzle_opening_0 = OpalPuzzleFactory.create(
            answer="0", hunt=hunt, num_to_unlock=0
        )
        puzzle_opening_1 = OpalPuzzleFactory.create(
            answer="1", hunt=hunt, num_to_unlock=0
        )
        puzzle_gated_2 = OpalPuzzleFactory.create(
            answer="2", hunt=hunt, num_to_unlock=2
        )
        puzzle_gated_3 = OpalPuzzleFactory.create(
            answer="3", hunt=hunt, num_to_unlock=3
        )

        with freeze_time("2024-08-01", tz_offset=0):
            self.assertFalse(hunt.has_started)
            self.assertFalse(puzzle_opening_0.can_view(alice))
            self.assertFalse(puzzle_opening_1.can_view(alice))
            self.assertFalse(puzzle_gated_2.can_view(alice))
            self.assertFalse(puzzle_gated_3.can_view(alice))
        with freeze_time("2024-10-01", tz_offset=0):
            self.assertTrue(hunt.has_started)

            # Hunt just started
            self.assertFalse(puzzle_opening_0.is_solved_by(alice))
            self.assertFalse(puzzle_opening_1.is_solved_by(alice))
            self.assertFalse(puzzle_gated_2.is_solved_by(alice))
            self.assertFalse(puzzle_gated_3.is_solved_by(alice))
            self.assertTrue(puzzle_opening_0.can_view(alice))
            self.assertTrue(puzzle_opening_1.can_view(alice))
            self.assertFalse(puzzle_gated_2.can_view(alice))
            self.assertFalse(puzzle_gated_3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 0)

            # Now let's solve puzzle 0 and send some wrong guesses for puzzle 1
            OpalAttemptFactory.create(user=alice, puzzle=puzzle_opening_0, guess="0")
            OpalAttemptFactory.create(
                user=alice, puzzle=puzzle_opening_1, guess="whisky"
            )
            OpalAttemptFactory.create(
                user=alice, puzzle=puzzle_opening_1, guess="tango"
            )
            OpalAttemptFactory.create(
                user=alice, puzzle=puzzle_opening_1, guess="foxtrot"
            )
            self.assertTrue(puzzle_opening_0.is_solved_by(alice))
            self.assertFalse(puzzle_opening_1.is_solved_by(alice))
            self.assertFalse(puzzle_gated_2.is_solved_by(alice))
            self.assertFalse(puzzle_gated_3.is_solved_by(alice))
            self.assertTrue(puzzle_opening_0.can_view(alice))
            self.assertTrue(puzzle_opening_1.can_view(alice))
            self.assertFalse(puzzle_gated_2.can_view(alice))
            self.assertFalse(puzzle_gated_3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 1)

            # Now let's solve puzzle 1
            OpalAttemptFactory.create(user=alice, puzzle=puzzle_opening_1, guess="1")
            self.assertTrue(puzzle_opening_0.is_solved_by(alice))
            self.assertTrue(puzzle_opening_1.is_solved_by(alice))
            self.assertFalse(puzzle_gated_2.is_solved_by(alice))
            self.assertFalse(puzzle_gated_3.is_solved_by(alice))
            self.assertTrue(puzzle_opening_0.can_view(alice))
            self.assertTrue(puzzle_opening_1.can_view(alice))
            self.assertTrue(puzzle_gated_2.can_view(alice))
            self.assertFalse(puzzle_gated_3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 2)

            # Finish puzzle 2
            OpalAttemptFactory.create(user=alice, puzzle=puzzle_gated_2, guess="2")
            self.assertTrue(puzzle_opening_0.is_solved_by(alice))
            self.assertTrue(puzzle_opening_1.is_solved_by(alice))
            self.assertTrue(puzzle_gated_2.is_solved_by(alice))
            self.assertFalse(puzzle_gated_3.is_solved_by(alice))
            self.assertTrue(puzzle_opening_0.can_view(alice))
            self.assertTrue(puzzle_opening_1.can_view(alice))
            self.assertTrue(puzzle_gated_2.can_view(alice))
            self.assertTrue(puzzle_gated_3.can_view(alice))
            self.assertEqual(hunt.num_solves(alice), 3)

            # But Bob is still at the start
            self.assertFalse(puzzle_opening_0.is_solved_by(bob))
            self.assertFalse(puzzle_opening_1.is_solved_by(bob))
            self.assertFalse(puzzle_gated_2.is_solved_by(bob))
            self.assertFalse(puzzle_gated_3.is_solved_by(bob))
            self.assertTrue(puzzle_opening_0.can_view(bob))
            self.assertTrue(puzzle_opening_1.can_view(bob))
            self.assertFalse(puzzle_gated_2.can_view(bob))
            self.assertFalse(puzzle_gated_3.can_view(bob))
            self.assertEqual(hunt.num_solves(bob), 0)
