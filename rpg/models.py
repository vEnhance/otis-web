import os
import random
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator  # NOQA
from django.db import models

from core.models import UnitGroup
from dashboard.models import validate_at_most_1mb  # should be in core maybe?  # NOQA
from roster.models import Student

# Create your models here.


def achievement_image_file_name(instance: "Achievement", filename: str) -> str:
    pk = instance.pk
    ext = os.path.splitext(filename)[-1]
    if pk is None:
        n = random.randrange(0, 2**64)
        basename = f"r{n:016x}"
    else:
        kludge = (settings.SECRET_KEY or "") + "_otis_diamond_" + str(pk)
        h = sha256(kludge.encode("ascii")).hexdigest()[0:24]
        basename = f"{pk:04d}_{h}"
    if filename.startswith("TESTING") and settings.TESTING is True:
        basename = "TESTING_" + basename
    return os.path.join("badges", basename + ext)


class Achievement(models.Model):
    code = models.CharField(
        max_length=96,
        unique=True,
        null=True,
        validators=[
            RegexValidator(regex=r"^[a-f0-9]{24,26}$", message="24-26 char hex string"),
        ],
    )  # e.g. 52656164546865436f646521
    name = models.CharField(
        max_length=128,
        help_text="Name of the achievement",
    )
    image = models.ImageField(
        upload_to=achievement_image_file_name,
        help_text="Image for the obtained achievement, at most 1MB.",
        null=True,
        blank=True,
        validators=[validate_at_most_1mb],
    )
    description = models.TextField(
        help_text="Text shown beneath this achievement for students who obtain it.",
        blank=True,
    )
    solution = models.TextField(
        help_text="Description of where the diamond is hidden",
        blank=True,
    )
    diamonds = models.SmallIntegerField(
        default=0,
        help_text="Number of diamonds for this achievement",
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="User who owns this achievement",
    )
    always_show_image = models.BooleanField(
        default=False,
        help_text="If enabled, always show the achievement image, even if no one earned the diamond yet.",
        verbose_name="Reveal",
    )

    class Meta:
        db_table = "dashboard_achievement"

    def __str__(self) -> str:
        return str(self.name)


class Level(models.Model):
    threshold = models.IntegerField(unique=True, help_text="The number of the level")
    name = models.CharField(max_length=128, help_text="The name of the level")

    class Meta:
        db_table = "dashboard_level"

    def __str__(self):
        return f"Level {self.threshold}: {self.name}"


class AchievementUnlock(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="The user who unlocked the achievement",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        help_text="The achievement that was obtained",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="The time the achievement was granted"
    )

    class Meta:
        db_table = "dashboard_achievementunlock"
        unique_together = (
            "user",
            "achievement",
        )

    def __str__(self) -> str:
        return self.timestamp.strftime("%c")


class QuestComplete(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, help_text="Student obtaining this reward"
    )
    title = models.CharField(max_length=160, help_text="A summary")
    spades = models.PositiveSmallIntegerField(help_text="The number of spades granted")
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="The time the achievement was granted"
    )

    CATEGORY_CHOICES = (
        ("PR", "Pull request"),
        ("BR", "Bug report"),
        ("VD", "Vulnerability disclosure"),
        ("WK", "Wiki bonus"),
        ("US", "USEMO Score"),
        ("UG", "USEMO Grading"),
        ("MS", "Miscellaneous"),
    )
    category = models.CharField(
        max_length=4,
        choices=CATEGORY_CHOICES,
        default="MS",
    )

    class Meta:
        db_table = "dashboard_questcomplete"

    def __str__(self) -> str:
        return self.title + " " + self.timestamp.strftime("%c")


class BonusLevel(models.Model):
    group = models.OneToOneField(UnitGroup, on_delete=models.CASCADE)
    level = models.PositiveSmallIntegerField(help_text="Level to spawn at")

    class Meta:
        db_table = "dashboard_bonuslevel"

    def __str__(self) -> str:
        return f"Lv. {self.level} Bonus"


class BonusLevelUnlock(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    bonus = models.ForeignKey(BonusLevel, on_delete=models.CASCADE)

    class Meta:
        db_table = "dashboard_bonuslevelunlock"

    def __str__(self) -> str:
        return self.timestamp.isoformat()


def palace_image_file_name(instance: "PalaceCarving", filename: str) -> str:
    del instance
    return os.path.join("palace", filename)


class PalaceCarving(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    display_name = models.CharField(
        max_length=128,
        help_text="How you would like your name to be displayed in the Ruby Palace.",
    )
    message = models.TextField(
        max_length=1024, help_text="You can write a message here", blank=True
    )
    hyperlink = models.URLField(help_text="An external link of your choice", blank=True)
    visible = models.BooleanField(
        help_text="Uncheck to hide your carving altogether (can change your mind later)",
        default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(
        upload_to=palace_image_file_name,
        help_text="Optional small photo that will appear next to your carving, no more than 1 megabyte",
        null=True,
        blank=True,
        validators=[validate_at_most_1mb],
    )

    class Meta:
        db_table = "dashboard_palacecarving"

    def __str__(self) -> str:
        return f"Palace carving for {self.display_name}"
