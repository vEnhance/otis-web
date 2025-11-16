import pytest

from core.factories import UserFactory
from roster.factories import StudentFactory
from rpg.models import QuestComplete

USEMO_SCORE_TEST_DATA = """Alice Aardvark\t42
Bob Beta\t14
Carol Cutie\t37"""
USEMO_GRADER_TEST_DATA = """Alice Aardvark
Bob Beta
Carol Cutie"""


@pytest.fixture
def mouse_setup(db):
    """Setup common data for mouse tests."""
    UserFactory.create(username="alice")
    UserFactory.create(username="evan", is_staff=True, is_superuser=True)

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


@pytest.mark.django_db
def test_usemo_score(otis, mouse_setup):
    otis.get_30x("usemo-score")  # anonymous redirected to login
    otis.login("alice")
    otis.get_40x("usemo-score")
    otis.login("evan")
    otis.get_20x("usemo-score")

    resp = otis.post_20x(
        "usemo-score",
        data={"text": USEMO_SCORE_TEST_DATA},
    )

    spades_list = QuestComplete.objects.filter(category="US").values_list(
        "spades", flat=True
    )
    assert len(spades_list) == 3
    assert set(spades_list) == {14, 37, 42}
    otis.assert_has(resp, "Built 3 records")


@pytest.mark.django_db
def test_usemo_grading(otis, mouse_setup):
    otis.get_30x("usemo-grader")  # anonymous redirected to login
    otis.login("alice")
    otis.get_40x("usemo-grader")
    otis.login("evan")
    otis.get_20x("usemo-grader")

    resp = otis.post_20x(
        "usemo-grader",
        data={"text": USEMO_SCORE_TEST_DATA},
    )

    spades_list = QuestComplete.objects.filter(category="UG").values_list(
        "spades", flat=True
    )
    otis.assert_has(resp, "Built 3 records")
    assert len(spades_list) == 3
    assert set(spades_list) == {15}
