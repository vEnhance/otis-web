import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from core.factories import GroupFactory, UnitFactory, UserFactory
from dashboard.factories import PSetFactory
from exams.factories import ExamAttemptFactory, PracticeExamFactory
from payments.factories import JobFactory, WorkerFactory
from roster.factories import StudentFactory
from roster.models import Student
from rpg.factories import (
    AchievementCodeGuessFactory,
    AchievementFactory,
    AchievementUnlockFactory,
    BonusLevelFactory,
    LevelFactory,
    QuestCompleteFactory,
    VulnerabilityRecordFactory,
)
from rpg.levelsys import (
    annotate_student_queryset_with_scores,
    get_level_info,
    get_student_rows,
)
from rpg.models import (
    GUESS_CODE_MAX_LENGTH,
    GUESS_WINDOW,
    WRONG_GUESS_LIMIT,
    Achievement,
    AchievementCodeGuess,
    AchievementUnlock,
)

UTC = datetime.UTC


@pytest.fixture
def alice_with_data(db):
    # Reset level factory sequence to ensure consistent threshold numbering
    LevelFactory.reset_sequence(0)

    verified_group = GroupFactory(name="Verified")
    alice = StudentFactory.create(
        user__username="alice",
        user__first_name="Alice",
        user__last_name="Aardvark",
        user__groups=(verified_group,),
    )
    PSetFactory.create(student=alice, clubs=120, hours=37, status="A", unit__code="BGW")
    PSetFactory.create(student=alice, clubs=100, hours=20, status="A", unit__code="DMX")
    PSetFactory.create(student=alice, clubs=180, hours=27, status="A", unit__code="ZCY")
    PSetFactory.create(student=alice, clubs=200, hours=87, status="P", unit__code="ZMR")
    AchievementUnlockFactory.create(
        user=alice.user, achievement__diamonds=4, achievement__name="Feel the fours"
    )
    AchievementUnlockFactory.create(
        user=alice.user, achievement__diamonds=7, achievement__name="Lucky number"
    )
    ExamAttemptFactory.create(student=alice, score=3)
    ExamAttemptFactory.create(student=alice, score=4)
    QuestCompleteFactory.create(student=alice, spades=5, title="Not problem six")
    LevelFactory.create_batch(size=50)
    return alice


def get_alice():
    return Student.objects.get(user__first_name="Alice", user__last_name="Aardvark")


@pytest.mark.django_db
def test_portal_loads(otis):
    alice = StudentFactory.create()
    otis.login(alice)
    otis.get_20x("portal", alice.pk)


@pytest.mark.django_db
def test_meter_update(alice_with_data):
    alice = get_alice()
    data = get_level_info(alice)
    assert data["meters"]["clubs"].level == 22
    assert data["meters"]["clubs"].value == 520
    assert data["meters"]["hearts"].level == 9
    assert data["meters"]["hearts"].value == 84
    assert data["meters"]["diamonds"].level == 3
    assert data["meters"]["diamonds"].value == 11
    assert data["meters"]["spades"].level == 4
    assert data["meters"]["spades"].value == 19
    assert data["level_number"] == 38
    assert data["level_name"] == "Level 38"


@pytest.mark.django_db
def test_portal_stats(otis, alice_with_data):
    alice = get_alice()
    otis.login(alice)
    resp = otis.get("portal", alice.pk)
    otis.assert_has(resp, "Level 38")
    otis.assert_has(resp, "520♣")
    otis.assert_has(resp, "84.0♥")
    otis.assert_has(resp, "11♦")
    otis.assert_has(resp, "19♠")


@pytest.mark.django_db
def test_stats_page(otis, alice_with_data):
    alice = get_alice()
    otis.login(alice)
    bob = StudentFactory.create()
    AchievementUnlockFactory.create(user=bob.user, achievement__name="FAIL THIS TEST")
    QuestCompleteFactory.create(student=bob, title="FAIL THIS TEST")

    resp = otis.get("stats", alice.pk)
    otis.assert_has(resp, "Level 38")
    otis.assert_has(resp, "520♣")
    otis.assert_has(resp, "84.0♥")
    otis.assert_has(resp, "11♦")
    otis.assert_has(resp, "19♠")
    otis.assert_has(resp, "Feel the fours")
    otis.assert_has(resp, "Not problem six")
    otis.assert_has(resp, "Lucky number")
    otis.assert_not_has(resp, "FAIL THIS TEST")


@pytest.mark.django_db
def test_level_up(otis, alice_with_data):
    alice = get_alice()
    otis.login(alice)
    bonus = BonusLevelFactory.create(group__name="Level 40 Quest", level=40)
    bonus_unit = UnitFactory.create(group=bonus.group, code="DKU")

    resp = otis.get_20x("portal", alice.pk)
    otis.assert_has(resp, "You&#x27;re now level 38.")
    otis.assert_not_has(resp, "Level 40 Quest")

    resp = otis.get_20x("portal", alice.pk)
    otis.assert_not_has(resp, "You&#x27;re now level 38.")
    otis.assert_not_has(resp, "Level 40 Quest")

    QuestCompleteFactory.create(student=alice, spades=24)

    resp = otis.get_20x("portal", alice.pk)
    otis.assert_has(resp, "You&#x27;re now level 40.")
    otis.assert_has(resp, "Level 40 Quest")

    resp = otis.get_20x("portal", alice.pk)
    otis.assert_not_has(resp, "You&#x27;re now level 40.")
    otis.assert_has(resp, "Level 40 Quest")

    QuestCompleteFactory.create(student=alice, spades=64)
    alice.curriculum.remove(bonus_unit)

    resp = otis.get_20x("portal", alice.pk)
    otis.assert_has(resp, "You&#x27;re now level 44.")
    otis.assert_not_has(resp, "Level 40 Quest")


@pytest.mark.django_db
def test_multi_student_annotate(otis, alice_with_data):
    alice = get_alice()
    bob = StudentFactory.create()
    carol = StudentFactory.create()
    donald = StudentFactory.create()

    # problem sets (clubs/hearts)
    PSetFactory.create(student=bob, clubs=196, hours=64, status="A", unit__code="DMW")
    PSetFactory.create(
        student=bob, clubs=None, hours=None, status="A", unit__code="ZMY"
    )

    # diamonds
    a1 = AchievementFactory.create(diamonds=3)
    a2 = AchievementFactory.create(diamonds=6)
    AchievementUnlockFactory.create(user=carol.user, achievement=a1)
    AchievementUnlockFactory.create(user=carol.user, achievement=a2)
    AchievementUnlockFactory.create(user=bob.user, achievement=a2)

    # spades
    exam = PracticeExamFactory.create()
    ExamAttemptFactory.create(student=bob, score=3, quiz=exam)
    ExamAttemptFactory.create(student=carol, score=4, quiz=exam)
    ExamAttemptFactory.create(student=carol, score=2)
    QuestCompleteFactory.create(student=carol, spades=5)

    worker_alice = WorkerFactory.create(user=alice.user)
    JobFactory.create(assignee=worker_alice, spades_bounty=2, progress="JOB_VFD")
    JobFactory.create(assignee=worker_alice, spades_bounty=5, progress="JOB_VFD")
    JobFactory.create(assignee=worker_alice, spades_bounty=9, progress="JOB_REV")
    worker_bob = WorkerFactory.create(user=bob.user)
    JobFactory.create(assignee=worker_bob, spades_bounty=4, progress="JOB_VFD")
    worker_donald = WorkerFactory.create(user=donald.user)
    JobFactory.create(assignee=worker_donald, spades_bounty=4, progress="JOB_NEW")

    # make levels
    LevelFactory.create_batch(size=36)

    queryset = annotate_student_queryset_with_scores(Student.objects.all())
    alice = queryset.get(pk=alice.pk)
    bob = queryset.get(pk=bob.pk)
    carol = queryset.get(pk=carol.pk)
    donald = queryset.get(pk=donald.pk)

    assert alice.num_psets == 3
    assert alice.clubs_any == 400
    assert alice.clubs_D == 100
    assert alice.clubs_Z == 180
    assert alice.hearts == 84
    assert alice.num_semesters == 1
    assert alice.spades_quizzes == 7
    assert alice.spades_quests == 5
    assert alice.spades_jobs == 7
    assert alice.diamonds == 11

    assert bob.num_psets == 2
    assert bob.clubs_any == 196
    assert bob.clubs_D == 196
    assert bob.clubs_Z is None
    assert bob.hearts == 64
    assert bob.num_semesters == 1
    assert bob.spades_quizzes == 3
    assert bob.spades_quests is None
    assert bob.spades_jobs == 4
    assert bob.diamonds == 6

    assert carol.num_psets == 0
    assert carol.clubs_any is None
    assert carol.clubs_D is None
    assert carol.clubs_Z is None
    assert carol.hearts is None
    assert carol.num_semesters == 1
    assert carol.spades_quizzes == 6
    assert carol.spades_quests == 5
    assert carol.spades_jobs is None
    assert carol.diamonds == 9

    assert donald.num_psets == 0
    assert donald.clubs_any is None
    assert donald.clubs_D is None
    assert donald.clubs_Z is None
    assert donald.hearts is None
    assert donald.num_semesters == 1
    assert donald.spades_quizzes is None
    assert donald.spades_quests is None
    assert donald.spades_jobs is None
    assert donald.diamonds is None

    rows = get_student_rows(queryset)
    rows.sort(key=lambda row: row["student"].pk)

    assert rows[0]["clubs"] == 520
    assert rows[0]["hearts"] == 84
    assert rows[0]["spades"] == 26
    assert rows[0]["diamonds"] == 11
    assert rows[0]["level"] == 39
    assert rows[0]["level_name"] == "Level 39"
    assert rows[0]["insanity"] == pytest.approx(0.25)

    assert rows[1]["clubs"] == pytest.approx(254.8)
    assert rows[1]["hearts"] == 64
    assert rows[1]["spades"] == 10
    assert rows[1]["diamonds"] == 6
    assert rows[1]["level"] == 28
    assert rows[1]["level_name"] == "Level 28"
    assert rows[1]["insanity"] == pytest.approx(0.5)

    assert rows[2]["clubs"] == 0
    assert rows[2]["hearts"] == 0
    assert rows[2]["spades"] == 17
    assert rows[2]["diamonds"] == 9
    assert rows[2]["level"] == 7
    assert rows[2]["level_name"] == "Level 7"
    assert rows[2]["insanity"] == pytest.approx(0)

    assert rows[3]["clubs"] == 0
    assert rows[3]["hearts"] == 0
    assert rows[3]["spades"] == 0
    assert rows[3]["diamonds"] == 0
    assert rows[3]["level"] == 0
    assert rows[3]["level_name"] == "No level"
    assert rows[3]["insanity"] == pytest.approx(0)

    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)
    otis.get_20x("leaderboard")


@pytest.mark.django_db
def test_submit_diamond_and_read_solution(otis, alice_with_data):
    alice = get_alice()
    bob = StudentFactory.create(
        user__first_name="Bob",
        user__last_name="Beta",
        semester=alice.semester,
    )
    a1 = AchievementFactory.create(diamonds=1)
    a2 = AchievementFactory.create(diamonds=2, creator=alice.user)
    a3 = AchievementFactory.create(diamonds=3, creator=bob.user)
    otis.login(alice.user)

    def alice_has(a: Achievement):
        return AchievementUnlock.objects.filter(achievement=a, user=alice.user).exists()

    # Submit a nonexistent code
    resp = otis.post_20x("stats", alice.pk, data={"code": "123456123456123456123456"})
    assert "You entered an invalid code." in resp.content.decode()
    assert not alice_has(a1)
    assert not alice_has(a2)
    assert not alice_has(a3)
    otis.get_40x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)  # because Alice owns it
    otis.get_40x("diamond-solution", a3.pk)

    # Submit a valid code for a1
    resp = otis.post_20x("stats", alice.pk, data={"code": a1.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" in resp.content.decode()
    assert alice_has(a1)
    assert not alice_has(a2)
    assert not alice_has(a3)
    otis.get_20x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)
    otis.get_40x("diamond-solution", a3.pk)

    # Submit a valid code for a1 that was obtained already
    resp = otis.post_20x("stats", alice.pk, data={"code": a1.code})
    assert "Already unlocked!" in resp.content.decode()
    assert alice_has(a1)
    assert not alice_has(a2)
    assert not alice_has(a3)
    otis.get_20x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)
    otis.get_40x("diamond-solution", a3.pk)

    # Submit a valid code for a2
    resp = otis.post_20x("stats", alice.pk, data={"code": a2.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" not in resp.content.decode()
    assert alice_has(a1)
    assert alice_has(a2)
    assert not alice_has(a3)
    otis.get_20x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)
    otis.get_40x("diamond-solution", a3.pk)

    # Submit a valid code for a2 that was obtained already
    resp = otis.post_20x("stats", alice.pk, data={"code": a2.code})
    assert "Already unlocked!" in resp.content.decode()
    assert alice_has(a1)
    assert alice_has(a2)
    assert not alice_has(a3)
    otis.get_20x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)
    otis.get_40x("diamond-solution", a3.pk)

    # Submit a valid code for a3
    resp = otis.post_20x("stats", alice.pk, data={"code": a3.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" in resp.content.decode()
    assert alice_has(a1)
    assert alice_has(a2)
    assert alice_has(a3)
    otis.get_20x("diamond-solution", a1.pk)
    otis.get_20x("diamond-solution", a2.pk)
    otis.get_20x("diamond-solution", a3.pk)

    # Test Bob, the owner of a3
    otis.login(bob.user)
    # Bob submits a1
    resp = otis.post_20x("stats", bob.pk, data={"code": a1.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" not in resp.content.decode()
    # Bob submits a2
    resp = otis.post_20x("stats", bob.pk, data={"code": a2.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" in resp.content.decode()
    # Bob submits a3
    resp = otis.post_20x("stats", bob.pk, data={"code": a3.code})
    assert "Achievement unlocked!" in resp.content.decode()
    assert "Wowie!" not in resp.content.decode()


@pytest.mark.django_db
def test_found_list(otis):
    alice = StudentFactory.create()
    a1 = AchievementFactory.create()
    a2 = AchievementFactory.create()
    AchievementUnlockFactory.create(user=alice.user, achievement=a1)
    AchievementUnlockFactory.create_batch(7, achievement=a1)
    AchievementUnlockFactory.create_batch(3, achievement=a2)

    # check students don't have access
    otis.login(alice.user)
    otis.get_40x("found-listing", a1.pk)
    otis.get_40x("found-listing", a2.pk)

    # login as staff now and check
    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)
    resp = otis.get_20x("found-listing", a1.pk)
    assert resp.context["unlocks_list"].count() == 8
    resp = otis.get_20x("found-listing", a2.pk)
    assert resp.context["unlocks_list"].count() == 3


@pytest.mark.django_db
def test_trader_list(otis):
    a1 = AchievementFactory.create(diamonds=1)
    a2 = AchievementFactory.create(diamonds=2)
    a3 = AchievementFactory.create(diamonds=3)
    a4 = AchievementFactory.create(diamonds=4)
    a5 = AchievementFactory.create(creator=UserFactory.create(), diamonds=5)
    a6 = AchievementFactory.create(creator=UserFactory.create(), diamonds=6)

    alice = StudentFactory.create()
    bob = StudentFactory.create()

    AchievementUnlockFactory.create(achievement=a1, user=alice.user)
    AchievementUnlockFactory.create(achievement=a1, user=bob.user)
    AchievementUnlockFactory.create(achievement=a2, user=alice.user)
    AchievementUnlockFactory.create(achievement=a3, user=bob.user)
    AchievementUnlockFactory.create(achievement=a5, user=alice.user)
    AchievementUnlockFactory.create(achievement=a6, user=bob.user)

    AchievementUnlockFactory.create_batch(10, achievement=a1)
    AchievementUnlockFactory.create_batch(20, achievement=a2)
    AchievementUnlockFactory.create_batch(30, achievement=a3)
    AchievementUnlockFactory.create_batch(5, achievement=a4)

    assert AchievementUnlock.objects.filter(user=alice.user).count() == 3
    otis.login(bob.user)


@pytest.mark.django_db
def test_palace(otis):
    alice = StudentFactory.create()
    otis.login(alice)
    LevelFactory.reset_sequence()
    LevelFactory.create_batch(size=5)

    for i in range(4):
        AchievementUnlockFactory.create(
            user=alice.user, achievement__diamonds=2 * i + 1
        )
        otis.assert_not_has(otis.get("portal", alice.pk), "Ruby Palace")
        otis.get_40x("palace-list", alice.pk)
        otis.get_40x("palace-update", alice.pk)
        otis.get_40x("diamond-update", alice.pk)
    AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=9)
    otis.assert_has(otis.get("portal", alice.pk), "Ruby Palace")
    otis.get_ok("palace-list", alice.pk)
    otis.get_ok("palace-update", alice.pk)
    otis.get_ok("diamond-update", alice.pk)


@pytest.mark.django_db
def test_github_landing(otis):
    vuls = VulnerabilityRecordFactory.create_batch(5)
    resp = otis.get_20x("github-landing")
    for v in vuls:
        assert v.finder_name in resp.content.decode()
        assert v.description in resp.content.decode()
        assert v.commit_hash in resp.content.decode()
        assert v.get_absolute_url() in resp.content.decode()
        assert v.get_absolute_url().endswith(v.commit_hash)


# --- is_first_obtain tests ---


@pytest.mark.django_db
def test_is_first_obtain_first_finder(otis):
    """First non-creator to submit a code gets is_first_obtain=True; subsequent finders get False."""
    alice = StudentFactory.create()
    bob = StudentFactory.create()
    achievement = AchievementFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    alice_unlock = AchievementUnlock.objects.get(
        user=alice.user, achievement=achievement
    )
    assert alice_unlock.is_first_obtain is True

    otis.login(bob)
    otis.post_20x("stats", bob.pk, data={"code": achievement.code})
    bob_unlock = AchievementUnlock.objects.get(user=bob.user, achievement=achievement)
    assert bob_unlock.is_first_obtain is False


@pytest.mark.django_db
def test_is_first_obtain_creator_unlock_skipped(otis):
    """Creator unlocking their own achievement is not counted as first find; the next non-creator is."""
    alice = StudentFactory.create()
    bob = StudentFactory.create()
    achievement = AchievementFactory.create(creator=alice.user)

    # Alice (the creator) submits first
    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    alice_unlock = AchievementUnlock.objects.get(
        user=alice.user, achievement=achievement
    )
    assert alice_unlock.is_first_obtain is False

    # Bob is the first non-creator finder
    otis.login(bob)
    otis.post_20x("stats", bob.pk, data={"code": achievement.code})
    bob_unlock = AchievementUnlock.objects.get(user=bob.user, achievement=achievement)
    assert bob_unlock.is_first_obtain is True


@pytest.mark.django_db
def test_is_first_obtain_creator_only(otis):
    """Creator unlocking their own achievement when no non-creator has found it yet: is_first_obtain=False."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create(creator=alice.user)

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    unlock = AchievementUnlock.objects.get(user=alice.user, achievement=achievement)
    assert unlock.is_first_obtain is False


@pytest.mark.django_db
def test_is_first_obtain_resubmit_unchanged(otis):
    """Re-submitting an already-obtained code does not change is_first_obtain."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    assert (
        AchievementUnlock.objects.get(
            user=alice.user, achievement=achievement
        ).is_first_obtain
        is True
    )

    # Submit again — should remain True
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    assert (
        AchievementUnlock.objects.get(
            user=alice.user, achievement=achievement
        ).is_first_obtain
        is True
    )


@pytest.mark.django_db
def test_is_first_obtain_bg_success_rendered(otis):
    """Stats page renders bg-success for achievements where is_first_obtain=True."""
    alice = StudentFactory.create()
    LevelFactory.reset_sequence(0)
    LevelFactory.create_batch(size=5)
    achievement = AchievementFactory.create(diamonds=1)
    AchievementUnlockFactory.create(
        user=alice.user, achievement=achievement, is_first_obtain=True
    )

    otis.login(alice)
    resp = otis.get_20x("stats", alice.pk)
    otis.assert_has(resp, "bg-success")


@pytest.mark.django_db
def test_is_first_obtain_no_bg_success_without_first_find(otis):
    """Stats page does not render bg-success when user has no first-obtain achievements."""
    alice = StudentFactory.create()
    LevelFactory.reset_sequence(0)
    LevelFactory.create_batch(size=5)
    achievement = AchievementFactory.create(diamonds=1)
    AchievementUnlockFactory.create(
        user=alice.user, achievement=achievement, is_first_obtain=False
    )

    otis.login(alice)
    resp = otis.get_20x("stats", alice.pk)
    otis.assert_not_has(resp, "bg-success")


# --- diamond code guess tests ---

WRONG_CODE = "123456123456123456123456"


def make_wrong_guesses(user: User, count: int):
    return AchievementCodeGuessFactory.create_batch(count, user=user)


@pytest.mark.django_db
def test_guesses_are_recorded(otis):
    """Both wrong and right guesses at diamond codes are saved to the database."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})

    wrong_guess, right_guess = AchievementCodeGuess.objects.filter(
        user=alice.user
    ).order_by("pk")
    assert wrong_guess.code == WRONG_CODE
    assert wrong_guess.is_correct is False
    assert wrong_guess.achievement is None
    assert wrong_guess.is_new_unlock is False
    assert right_guess.code == achievement.code
    assert right_guess.is_correct is True
    assert right_guess.achievement == achievement
    assert right_guess.is_new_unlock is True


@pytest.mark.django_db
def test_repeat_redeem_is_marked(otis):
    """A code entered a second time is recorded, but not as earning anything."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    resp = otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    otis.assert_has(resp, "Already unlocked!")

    earned, repeat = AchievementCodeGuess.objects.filter(user=alice.user).order_by("pk")
    assert earned.is_new_unlock is True
    assert repeat.is_new_unlock is False
    # the repeat is still a correct guess; it just didn't earn the diamond
    assert repeat.is_correct is True
    assert repeat.achievement == achievement


@pytest.mark.django_db
def test_creator_redeeming_own_code_earns_it_once(otis):
    """The first redeem is marked even when the guesser created the diamond."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create(creator=alice.user)

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})

    earned, repeat = AchievementCodeGuess.objects.filter(user=alice.user).order_by("pk")
    assert earned.is_new_unlock is True
    assert repeat.is_new_unlock is False


@pytest.mark.django_db
def test_wrong_guesses_are_rate_limited(otis):
    """After WRONG_GUESS_LIMIT wrong guesses, further guesses are refused."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT - 1)

    otis.login(alice)
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(resp, "You entered an invalid code.")

    # the limit is now used up, so even a correct code is turned away
    resp = otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    otis.assert_has(
        resp, f"You&#x27;ve used up your {WRONG_GUESS_LIMIT} incorrect guesses."
    )
    assert not AchievementUnlock.objects.filter(
        user=alice.user, achievement=achievement
    ).exists()
    # ... and the refused guess isn't recorded either
    assert AchievementCodeGuess.objects.filter(user=alice.user).count() == (
        WRONG_GUESS_LIMIT
    )


@pytest.mark.django_db
def test_rate_limit_is_per_user(otis):
    """One user using up their guesses doesn't affect anyone else."""
    alice = StudentFactory.create()
    bob = StudentFactory.create()
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT)

    otis.login(bob)
    resp = otis.post_20x("stats", bob.pk, data={"code": WRONG_CODE})
    otis.assert_has(resp, "You entered an invalid code.")


@pytest.mark.django_db
def test_rate_limit_forgets_old_guesses(otis):
    """Wrong guesses older than GUESS_WINDOW don't count against the limit."""
    alice = StudentFactory.create()
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT)
    AchievementCodeGuess.objects.filter(user=alice.user).update(
        timestamp=timezone.now() - GUESS_WINDOW - datetime.timedelta(minutes=1)
    )

    otis.login(alice)
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(resp, "You entered an invalid code.")


@pytest.mark.django_db
def test_new_unlock_resets_rate_limit(otis):
    """Earning a diamond wipes the slate of wrong guesses counted so far."""
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT - 1)

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    assert AchievementUnlock.objects.filter(
        user=alice.user, achievement=achievement
    ).exists()

    # the wrong guesses before the unlock no longer count
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT - 1)
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(resp, "You entered an invalid code.")

    # but the ones after it do
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(
        resp, f"You&#x27;ve used up your {WRONG_GUESS_LIMIT} incorrect guesses."
    )


@pytest.mark.django_db
def test_repeat_of_owned_code_does_not_reset_rate_limit(otis):
    """Retyping a code you already own doesn't buy you a fresh set of guesses.

    Every student is shown a working code on this very page, so a reset that
    any correct submission could trigger would be no rate limit at all.
    """
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT - 1)

    # submitting the owned code again is still a correct guess, but unlocks nothing
    resp = otis.post_20x("stats", alice.pk, data={"code": achievement.code})
    otis.assert_has(resp, "Already unlocked!")
    assert (
        AchievementCodeGuess.objects.filter(user=alice.user, is_correct=True).count()
        == 2
    )

    # so the earlier wrong guesses still count: one left, then the limit bites
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(resp, "You entered an invalid code.")
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(
        resp, f"You&#x27;ve used up your {WRONG_GUESS_LIMIT} incorrect guesses."
    )


@pytest.mark.django_db
def test_malformed_guesses_are_recorded(otis):
    """Submissions that aren't shaped like a code are recorded but never looked up."""
    alice = StudentFactory.create()

    otis.login(alice)
    resp = otis.post_20x("stats", alice.pk, data={"code": "not a hex code"})
    otis.assert_has(resp, "This doesn&#x27;t appear to be a hex code.")

    guess = AchievementCodeGuess.objects.get(user=alice.user)
    assert guess.code == "not a hex code"
    assert guess.is_well_formed is False
    assert guess.is_correct is False
    assert guess.is_new_unlock is False
    assert guess.achievement is None


@pytest.mark.django_db
def test_overlong_guess_is_truncated(otis):
    """An absurdly long submission is stored, cut down to the column width."""
    alice = StudentFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": "f" * 500})

    guess = AchievementCodeGuess.objects.get(user=alice.user)
    assert guess.code == "f" * GUESS_CODE_MAX_LENGTH
    assert guess.is_well_formed is False


@pytest.mark.django_db
def test_empty_guess_is_not_recorded(otis):
    """Submitting the form with nothing in it isn't a guess at all."""
    alice = StudentFactory.create()

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": "   "})

    assert not AchievementCodeGuess.objects.filter(user=alice.user).exists()


@pytest.mark.django_db
def test_malformed_guesses_count_against_rate_limit(otis):
    """Garbage submissions burn guesses just like wrong codes do."""
    alice = StudentFactory.create()
    make_wrong_guesses(alice.user, WRONG_GUESS_LIMIT - 1)

    otis.login(alice)
    otis.post_20x("stats", alice.pk, data={"code": "not a hex code"})
    resp = otis.post_20x("stats", alice.pk, data={"code": WRONG_CODE})
    otis.assert_has(
        resp, f"You&#x27;ve used up your {WRONG_GUESS_LIMIT} incorrect guesses."
    )
