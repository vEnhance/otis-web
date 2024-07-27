from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.urls.base import reverse
from django.utils import timezone
from django.utils.http import urlencode


class HanabiPlayer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    hanab_username = models.CharField(
        max_length=64,
        help_text="The username you use on hanab.live.",
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.hanab_username

    @property
    def name(self) -> str:
        return self.user.get_full_name()


class ActiveHanabiContestManager(models.Manager):
    def get_queryset(self) -> QuerySet["HanabiContest"]:
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .filter(
                start_date__lte=now,
                end_date__gte=now,
            )
        )


class UpcomingHanabiContestManager(models.Manager):
    def get_queryset(self) -> QuerySet["HanabiContest"]:
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .filter(
                start_date__lte=now + timedelta(days=30),
            )
        )


class HanabiContest(models.Model):
    variant_id = models.PositiveIntegerField(help_text="The variant ID on hanab.live")
    variant_name = models.CharField(
        max_length=64, help_text="The variant being played as a string."
    )
    num_players = models.PositiveSmallIntegerField(
        help_text="The number of players.",
        default=3,
    )
    num_suits = models.PositiveSmallIntegerField(
        help_text="The number of suits.",
        default=5,
    )
    start_date = models.DateTimeField(help_text="When the contest becomes visible.")
    end_date = models.DateTimeField(help_text="The end_date to play this seed.")
    processed = models.BooleanField(
        help_text="Whether the results have been processed",
        default=False,
    )

    objects = models.Manager()
    active = ActiveHanabiContestManager()
    upcoming = UpcomingHanabiContestManager()

    class Meta:
        ordering = ("-end_date",)

    def __str__(self) -> str:
        return f"Contest #{self.pk}: {self.variant_name}"

    def get_absolute_url(self) -> str:
        return reverse("hanabi-replays", args=(self.pk,))

    @property
    def seed_name(self) -> str:
        return f"otis{self.pk}"

    @property
    def full_seed_name(self) -> str:
        return f"p{self.num_players}v{self.variant_id}sotis{self.pk}"

    @property
    def hanab_stats_page_url(self) -> str:
        return f"https://hanab.live/seed/{self.full_seed_name}"

    @property
    def create_table_url(self) -> str:
        return r"https://hanab.live/create-table?" + urlencode(
            {
                "name": f"!seed {self.seed_name}",
                "variantName": self.variant_name,
                "timed": "true",
                "timeBase": "180",
                "timePerTurn": "30",
            }
        )

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.end_date

    @property
    def is_upcoming(self) -> bool:
        return timezone.now() <= self.start_date

    @property
    def max_score(self) -> int:
        return 5 * self.num_suits


class HanabiReplay(models.Model):
    contest = models.ForeignKey(HanabiContest, on_delete=models.CASCADE)
    replay_id = models.PositiveIntegerField(
        help_text="The ID of the replay.",
        unique=True,
    )
    game_score = models.PositiveIntegerField(help_text="The game score.")
    turn_count = models.PositiveIntegerField(help_text="The number of turns elapsed.")
    spades_score = models.FloatField(
        help_text="The number of spades obtained.", null=True, blank=True
    )

    def __str__(self) -> str:
        return f"Replay #{self.replay_id}"

    def get_absolute_url(self) -> str:
        return f"https://hanab.live/replay/{self.replay_id}"

    def get_base_spades(self) -> float:
        num_suits = self.contest.num_suits
        return 4 * (self.game_score / (5 * num_suits)) ** 4


class HanabiParticipation(models.Model):
    player = models.ForeignKey(HanabiPlayer, on_delete=models.CASCADE)
    replay = models.ForeignKey(HanabiReplay, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("player", "replay")

    def __str__(self) -> str:
        return f"{self.player.hanab_username} in #{self.replay.replay_id}"
