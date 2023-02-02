from django.contrib.auth.models import User
from django.db import models
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


class HanabiContest(models.Model):
    variant_name = models.CharField(
        max_length=64, help_text="The variant being played as a string."
    )
    num_players = models.PositiveSmallIntegerField(help_text="The number of players.")
    num_suits = models.PositiveSmallIntegerField(
        help_text="The number of suits.", default=5
    )
    start_date = models.DateTimeField(help_text="When the contest becomes visible.")
    deadline = models.DateTimeField(help_text="The deadline to play this seed.")
    processed = models.BooleanField(
        help_text="Whether the results have been processed", default=False
    )

    class Meta:
        ordering = ("-deadline",)

    def __str__(self) -> str:
        return f"Contest #{self.pk}: {self.variant_name}"

    def get_absolute_url(self) -> str:
        return reverse("hanabi-replays", args=(self.pk,))

    @property
    def seed_name(self) -> str:
        return f"otis{self.pk}"

    @property
    def create_table_url(self) -> str:
        return r"https://hanab.live/create-table?" + urlencode(
            {
                "name": f"!seed {self.seed_name}",
                "variantName": self.variant_name,
                "timed": "true",
                "timeBase": "120",
                "timePerTurn": "20",
            }
        )

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.deadline


class HanabiReplay(models.Model):
    contest = models.ForeignKey(HanabiContest, on_delete=models.CASCADE)
    replay_id = models.PositiveIntegerField(
        help_text="The ID of the replay.",
        unique=True,
    )
    game_score = models.PositiveIntegerField(help_text="The game score.")
    turn_count = models.PositiveIntegerField(help_text="The number of turns elapsed.")
    spades_score = models.FloatField(help_text="The number of spades obtained.")

    def __str__(self) -> str:
        return f"Replay #{self.replay_id}"

    def get_absolute_url(self) -> str:
        return f"https://hanab.live/replay/{self.replay_id}"


class HanabiParticipation(models.Model):
    player = models.ForeignKey(HanabiPlayer, on_delete=models.CASCADE)
    replay = models.ForeignKey(HanabiReplay, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("player", "replay")
