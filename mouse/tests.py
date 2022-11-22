from core.factories import UserFactory
from evans_django_tools.testsuite import EvanTestCase
from roster.factories import StudentFactory
from rpg.models import QuestComplete

USEMO_SCORE_TEST_DATA = """Alice Aardvark\t42
Bob Beta\t14
Carol Cutie\t37"""
USEMO_GRADER_TEST_DATA = """Alice Aardvark
Bob Beta
Carol Cutie"""


class MouseTests(EvanTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        UserFactory.create(username='alice')
        UserFactory.create(username='evan', is_staff=True, is_superuser=True)

        StudentFactory.create(
            user__first_name="Alice",
            user__last_name="Aardvark",
            semester__active=True,
        )
        StudentFactory.create(
            user__first_name="Bob",
            user__last_name="Beta",
            semester__active=True,
        )
        StudentFactory.create(
            user__first_name="Carol",
            user__last_name="Cutie",
            semester__active=True,
        )

    def test_usemo_score(self):
        self.assertGetBecomesStaffRedirect('usemo-score')
        self.login('alice')
        self.assertGetBecomesStaffRedirect('usemo-grader')
        self.login('evan')
        self.assertGet20X('usemo-grader')

        resp = self.assertPost20X(
            'usemo-score',
            data={'text': USEMO_SCORE_TEST_DATA},
        )

        spades_list = QuestComplete.objects\
                .filter(category="US").values_list('spades', flat=True)
        self.assertEqual(len(spades_list), 3)
        self.assertEqual(set(spades_list), {14, 37, 42})
        self.assertHas(resp, 'Built 3 records')

    def test_usemo_grading(self):
        self.assertGetBecomesStaffRedirect('usemo-grader')
        self.login('alice')
        self.assertGetBecomesStaffRedirect('usemo-grader')
        self.login('evan')
        self.assertGet20X('usemo-grader')

        resp = self.assertPost20X(
            'usemo-grader',
            data={'text': USEMO_SCORE_TEST_DATA},
        )

        spades_list = QuestComplete.objects\
                .filter(category="UG").values_list('spades', flat=True)
        self.assertHas(resp, 'Built 3 records')
        self.assertEqual(len(spades_list), 3)
        self.assertEqual(set(spades_list), {15})
