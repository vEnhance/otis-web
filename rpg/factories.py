from core.factories import UnitGroupFactory, UserFactory  # NOQA
from evans_django_tools.testsuite import UniqueFaker
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory, ImageField
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from roster.factories import StudentFactory

from .models import (
    Achievement,
    AchievementUnlock,
    BonusLevel,
    BonusLevelUnlock,
    Level,
    QuestComplete,
)  # NOQA


class AchievementFactory(DjangoModelFactory):
    class Meta:
        model = Achievement

    code = UniqueFaker("bban")
    name = Faker("job")
    image = ImageField(filename="TESTING_achievement_icon.png")
    description = UniqueFaker("sentence")


class LevelFactory(DjangoModelFactory):
    class Meta:
        model = Level

    threshold = Sequence(lambda n: n + 1)
    name = LazyAttribute(lambda o: f"Level {o.threshold}")


class AchievementUnlockFactory(DjangoModelFactory):
    class Meta:
        model = AchievementUnlock

    user = SubFactory(UserFactory)
    achievement = SubFactory(AchievementFactory)


class QuestCompleteFactory(DjangoModelFactory):
    class Meta:
        model = QuestComplete

    student = SubFactory(StudentFactory)
    title = Faker("job")
    spades = FuzzyChoice(list(range(1, 10)))


class BonusLevelFactory(DjangoModelFactory):
    class Meta:
        model = BonusLevel

    level = 100
    group = SubFactory(UnitGroupFactory)


class BonusLevelUnlockFactory(DjangoModelFactory):
    class Meta:
        model = BonusLevelUnlock

    student = SubFactory(StudentFactory)
    level = SubFactory(BonusLevelFactory)
