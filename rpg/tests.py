from django.utils import timezone

from core.factories import GroupFactory, UnitFactory, UserFactory
from dashboard.factories import PSetFactory
from evans_django_tools.testsuite import EvanTestCase
from exams.factories import ExamAttemptFactory, TestFactory
from payments.factories import JobFactory, WorkerFactory
from roster.factories import StudentFactory
from roster.models import Student
from rpg.factories import (  # NOQA
    AchievementFactory,
    AchievementUnlockFactory,
    BonusLevelFactory,
    LevelFactory,
    QuestCompleteFactory,
    VulnerabilityRecordFactory,
)
from rpg.levelsys import (  # NOQA
    annotate_student_queryset_with_scores,
    get_level_info,
    get_student_rows,
)
from rpg.models import Achievement, AchievementUnlock

utc = timezone.utc


class TestLevelSystem(EvanTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        verified_group = GroupFactory(name="Verified")
        alice = StudentFactory.create(
            user__username="alice",
            user__first_name="Alice",
            user__last_name="Aardvark",
            user__groups=(verified_group,),
        )
        PSetFactory.create(
            student=alice, clubs=120, hours=37, status="A", unit__difficulty="B"
        )
        PSetFactory.create(
            student=alice, clubs=100, hours=20, status="A", unit__difficulty="D"
        )
        PSetFactory.create(
            student=alice, clubs=180, hours=27, status="A", unit__difficulty="Z"
        )
        PSetFactory.create(
            student=alice, clubs=200, hours=87, status="P", unit__difficulty="Z"
        )        
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

    def get_alice(self):
        return Student.objects.get(user__first_name="Alice", user__last_name="Aardvark")

    def test_portal_loads(self):
        alice = StudentFactory.create()
        self.login(alice)
        self.assertGet20X("portal", alice.pk)

    def test_meter_update(self):
        alice = self.get_alice()
        data = get_level_info(alice)
        self.assertEqual(data["meters"]["clubs"].level, 22)
        self.assertEqual(data["meters"]["clubs"].value, 520)
        self.assertEqual(data["meters"]["hearts"].level, 9)
        self.assertEqual(data["meters"]["hearts"].value, 84)
        self.assertEqual(data["meters"]["diamonds"].level, 3)
        self.assertEqual(data["meters"]["diamonds"].value, 11)
        self.assertEqual(data["meters"]["spades"].level, 4)
        self.assertEqual(data["meters"]["spades"].value, 19)
        self.assertEqual(data["level_number"], 38)
        self.assertEqual(data["level_name"], "Level 38")

    def test_portal_stats(self):
        alice = self.get_alice()
        self.login(alice)
        resp = self.get("portal", alice.pk)
        self.assertHas(resp, "Level 38")
        self.assertHas(resp, "520♣")
        self.assertHas(resp, "84.0♥")
        self.assertHas(resp, "11♦")
        self.assertHas(resp, "19♠")

    def test_stats_page(self):
        alice = self.get_alice()
        self.login(alice)
        bob = StudentFactory.create()
        AchievementUnlockFactory.create(
            user=bob.user, achievement__name="FAIL THIS TEST"
        )
        QuestCompleteFactory.create(student=bob, title="FAIL THIS TEST")

        resp = self.get("stats", alice.pk)
        self.assertHas(resp, "Level 38")
        self.assertHas(resp, "520♣")
        self.assertHas(resp, "84.0♥")
        self.assertHas(resp, "11♦")
        self.assertHas(resp, "19♠")
        self.assertHas(resp, "Feel the fours")
        self.assertHas(resp, "Not problem six")
        self.assertHas(resp, "Lucky number")
        self.assertNotHas(resp, "FAIL THIS TEST")

    def test_level_up(self):
        alice = self.get_alice()
        self.login(alice)
        bonus = BonusLevelFactory.create(group__name="Level 40 Quest", level=40)
        bonus_unit = UnitFactory.create(group=bonus.group, difficulty="D")

        resp = self.assertGet20X("portal", alice.pk)
        self.assertHas(resp, "You&#x27;re now level 38.")
        self.assertNotHas(resp, "Level 40 Quest")

        resp = self.assertGet20X("portal", alice.pk)
        self.assertNotHas(resp, "You&#x27;re now level 38.")
        self.assertNotHas(resp, "Level 40 Quest")

        QuestCompleteFactory.create(student=alice, spades=24)

        resp = self.assertGet20X("portal", alice.pk)
        self.assertHas(resp, "You&#x27;re now level 40.")
        self.assertHas(resp, "Level 40 Quest")

        resp = self.assertGet20X("portal", alice.pk)
        self.assertNotHas(resp, "You&#x27;re now level 40.")
        self.assertHas(resp, "Level 40 Quest")

        QuestCompleteFactory.create(student=alice, spades=64)
        alice.curriculum.remove(bonus_unit)

        resp = self.assertGet20X("portal", alice.pk)
        self.assertHas(resp, "You&#x27;re now level 44.")
        self.assertNotHas(resp, "Level 40 Quest")

    def test_multi_student_annotate(self):
        alice = self.get_alice()
        bob = StudentFactory.create()
        carol = StudentFactory.create()
        donald = StudentFactory.create()

        # problem sets (clubs/hearts)
        PSetFactory.create(student=bob, clubs=196, hours=64, status="A", unit__difficulty="D")
        PSetFactory.create(student=bob, clubs=None, hours=None, status="A", unit__difficulty="Z")

        # diamonds
        a1 = AchievementFactory.create(diamonds=3)
        a2 = AchievementFactory.create(diamonds=6)
        AchievementUnlockFactory.create(user=carol.user, achievement=a1)
        AchievementUnlockFactory.create(user=carol.user, achievement=a2)
        AchievementUnlockFactory.create(user=bob.user, achievement=a2)

        # spades
        exam = TestFactory.create()
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

        self.assertEqual(getattr(alice, "num_psets"), 3)
        self.assertEqual(getattr(alice, "clubs_any"), 400)
        self.assertEqual(getattr(alice, "clubs_D"), 100)
        self.assertEqual(getattr(alice, "clubs_Z"), 180)
        self.assertEqual(getattr(alice, "hearts"), 84)
        self.assertEqual(getattr(alice, "spades_quizzes"), 7)
        self.assertEqual(getattr(alice, "spades_quests"), 5)
        self.assertEqual(getattr(alice, "spades_jobs"), 7)
        self.assertEqual(getattr(alice, "diamonds"), 11)

        self.assertEqual(getattr(bob, "num_psets"), 2)
        self.assertEqual(getattr(bob, "clubs_any"), 196)
        self.assertEqual(getattr(bob, "clubs_D"), 196)
        self.assertEqual(getattr(bob, "clubs_Z"), None)
        self.assertEqual(getattr(bob, "hearts"), 64)
        self.assertEqual(getattr(bob, "spades_quizzes"), 3)
        self.assertEqual(getattr(bob, "spades_quests"), None)
        self.assertEqual(getattr(bob, "spades_jobs"), 4)
        self.assertEqual(getattr(bob, "diamonds"), 6)

        self.assertEqual(getattr(carol, "num_psets"), 0)
        self.assertEqual(getattr(carol, "clubs_any"), None)
        self.assertEqual(getattr(carol, "clubs_D"), None)
        self.assertEqual(getattr(carol, "clubs_Z"), None)
        self.assertEqual(getattr(carol, "hearts"), None)
        self.assertEqual(getattr(carol, "spades_quizzes"), 6)
        self.assertEqual(getattr(carol, "spades_quests"), 5)
        self.assertEqual(getattr(carol, "spades_jobs"), None)
        self.assertEqual(getattr(carol, "diamonds"), 9)

        self.assertEqual(getattr(donald, "num_psets"), 0)
        self.assertEqual(getattr(donald, "clubs_any"), None)
        self.assertEqual(getattr(donald, "clubs_D"), None)
        self.assertEqual(getattr(donald, "clubs_Z"), None)
        self.assertEqual(getattr(donald, "hearts"), None)
        self.assertEqual(getattr(donald, "spades_quizzes"), None)
        self.assertEqual(getattr(donald, "spades_quests"), None)
        self.assertEqual(getattr(donald, "spades_jobs"), None)
        self.assertEqual(getattr(donald, "diamonds"), None)

        rows = get_student_rows(queryset)
        rows.sort(key=lambda row: row["student"].pk)

        self.assertEqual(rows[0]["clubs"], 520)
        self.assertEqual(rows[0]["hearts"], 84)
        self.assertEqual(rows[0]["spades"], 26)
        self.assertEqual(rows[0]["diamonds"], 11)
        self.assertEqual(rows[0]["level"], 39)
        self.assertEqual(rows[0]["level_name"], "Level 39")
        self.assertAlmostEqual(rows[0]["insanity"], 0.25)

        self.assertAlmostEqual(rows[1]["clubs"], 254.8)
        self.assertEqual(rows[1]["hearts"], 64)
        self.assertEqual(rows[1]["spades"], 10)
        self.assertEqual(rows[1]["diamonds"], 6)
        self.assertEqual(rows[1]["level"], 28)
        self.assertEqual(rows[1]["level_name"], "Level 28")
        self.assertAlmostEqual(rows[1]["insanity"], 0.5)

        self.assertEqual(rows[2]["clubs"], 0)
        self.assertEqual(rows[2]["hearts"], 0)
        self.assertEqual(rows[2]["spades"], 17)
        self.assertEqual(rows[2]["diamonds"], 9)
        self.assertEqual(rows[2]["level"], 7)
        self.assertEqual(rows[2]["level_name"], "Level 7")
        self.assertAlmostEqual(rows[2]["insanity"], 0)

        self.assertEqual(rows[3]["clubs"], 0)
        self.assertEqual(rows[3]["hearts"], 0)
        self.assertEqual(rows[3]["spades"], 0)
        self.assertEqual(rows[3]["diamonds"], 0)
        self.assertEqual(rows[3]["level"], 0)
        self.assertEqual(rows[3]["level_name"], "No level")
        self.assertAlmostEqual(rows[3]["insanity"], 0)

        admin = UserFactory.create(is_staff=True, is_superuser=True)
        self.login(admin)
        self.assertGet20X("leaderboard")

    def test_submit_diamond_and_read_solution(self):
        alice = self.get_alice()
        bob = StudentFactory.create(
            user__first_name="Bob",
            user__last_name="Beta",
            semester=alice.semester,
        )
        a1 = AchievementFactory.create(diamonds=1)
        a2 = AchievementFactory.create(diamonds=2, creator=alice.user)
        a3 = AchievementFactory.create(diamonds=3, creator=bob.user)
        self.login(alice.user)

        def alice_has(a: Achievement):
            return AchievementUnlock.objects.filter(
                achievement=a, user=alice.user
            ).exists()

        # Submit a nonexistent code
        resp = self.assertPost20X(
            "stats", alice.pk, data={"code": "123456123456123456123456"}
        )
        self.assertContains(resp, "You entered an invalid code.")
        self.assertFalse(alice_has(a1))
        self.assertFalse(alice_has(a2))
        self.assertFalse(alice_has(a3))
        self.assertGet40X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)  # because Alice owns it
        self.assertGet40X("diamond-solution", a3.pk)

        # Submit a valid code for a1
        resp = self.assertPost20X("stats", alice.pk, data={"code": a1.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertContains(resp, "Wowie!")
        self.assertTrue(alice_has(a1))
        self.assertFalse(alice_has(a2))
        self.assertFalse(alice_has(a3))
        self.assertGet20X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)
        self.assertGet40X("diamond-solution", a3.pk)

        # Submit a valid code for a1 that was obtained already
        resp = self.assertPost20X("stats", alice.pk, data={"code": a1.code})
        self.assertContains(resp, "Already unlocked!")
        self.assertTrue(alice_has(a1))
        self.assertFalse(alice_has(a2))
        self.assertFalse(alice_has(a3))
        self.assertGet20X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)
        self.assertGet40X("diamond-solution", a3.pk)

        # Submit a valid code for a2
        resp = self.assertPost20X("stats", alice.pk, data={"code": a2.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertNotContains(resp, "Wowie!")
        self.assertTrue(alice_has(a1))
        self.assertTrue(alice_has(a2))
        self.assertFalse(alice_has(a3))
        self.assertGet20X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)
        self.assertGet40X("diamond-solution", a3.pk)

        # Submit a valid code for a2 that was obtained already
        resp = self.assertPost20X("stats", alice.pk, data={"code": a2.code})
        self.assertContains(resp, "Already unlocked!")
        self.assertTrue(alice_has(a1))
        self.assertTrue(alice_has(a2))
        self.assertFalse(alice_has(a3))
        self.assertGet20X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)
        self.assertGet40X("diamond-solution", a3.pk)

        # Submit a valid code for a3
        resp = self.assertPost20X("stats", alice.pk, data={"code": a3.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertContains(resp, "Wowie!")
        self.assertTrue(alice_has(a1))
        self.assertTrue(alice_has(a2))
        self.assertTrue(alice_has(a3))
        self.assertGet20X("diamond-solution", a1.pk)
        self.assertGet20X("diamond-solution", a2.pk)
        self.assertGet20X("diamond-solution", a3.pk)

        # Test Bob, the owner of a3
        self.login(bob.user)
        # Bob submits a1
        resp = self.assertPost20X("stats", bob.pk, data={"code": a1.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertNotContains(resp, "Wowie!")
        # Bob submits a2
        resp = self.assertPost20X("stats", bob.pk, data={"code": a2.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertContains(resp, "Wowie!")
        # Bob submits a3
        resp = self.assertPost20X("stats", bob.pk, data={"code": a3.code})
        self.assertContains(resp, "Achievement unlocked!")
        self.assertNotContains(resp, "Wowie!")


class TestAchievements(EvanTestCase):
    def test_found_list(self):
        alice = StudentFactory.create()
        a1 = AchievementFactory.create()
        a2 = AchievementFactory.create()
        AchievementUnlockFactory.create(user=alice.user, achievement=a1)
        AchievementUnlockFactory.create_batch(7, achievement=a1)
        AchievementUnlockFactory.create_batch(3, achievement=a2)

        # check students don't have access
        self.login(alice.user)
        self.assertGet40X("found-listing", a1.pk)
        self.assertGet40X("found-listing", a2.pk)

        # login as staff now and check
        admin = UserFactory.create(is_staff=True, is_superuser=True)
        self.login(admin)
        resp = self.assertGet20X("found-listing", a1.pk)
        self.assertEqual(resp.context["unlocks_list"].count(), 8)
        resp = self.assertGet20X("found-listing", a2.pk)
        self.assertEqual(resp.context["unlocks_list"].count(), 3)

    def test_trader_list(self):
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

        self.assertEqual(AchievementUnlock.objects.filter(user=alice.user).count(), 3)
        self.login(bob.user)


class TestPalace(EvanTestCase):
    def test_palace(self):
        alice = StudentFactory.create()
        self.login(alice)
        LevelFactory.reset_sequence()
        LevelFactory.create_batch(size=5)

        for i in range(0, 4):
            AchievementUnlockFactory.create(
                user=alice.user, achievement__diamonds=2 * i + 1
            )
            self.assertNotHas(self.get("portal", alice.pk), "Ruby Palace")
            self.assertGet40X("palace-list", alice.pk, follow=True)
            self.assertGet40X("palace-update", alice.pk, follow=True)
            self.assertGet40X("diamond-update", alice.pk, follow=True)
        AchievementUnlockFactory.create(user=alice.user, achievement__diamonds=9)
        self.assertHas(self.get("portal", alice.pk), "Ruby Palace")
        self.assertGetOK("palace-list", alice.pk)
        self.assertGetOK("palace-update", alice.pk)
        self.assertGetOK("diamond-update", alice.pk)


class TestGithubLanding(EvanTestCase):
    def test_github_landing(self):
        vuls = VulnerabilityRecordFactory.create_batch(5)
        resp = self.assertGet20X("github-landing")
        for v in vuls:
            self.assertContains(resp, v.finder_name)
            self.assertContains(resp, v.description)
            self.assertContains(resp, v.commit_hash)
            self.assertContains(resp, v.get_absolute_url())
            self.assertTrue(v.get_absolute_url().endswith(v.commit_hash))
