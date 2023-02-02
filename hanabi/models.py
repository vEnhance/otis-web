from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class HanabiPlayer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hanab_username = models.CharField(
        max_length=64,
        help_text="The username you use on hanab.live.",
        unique=True,
    )


class HanabiContest(models.Model):
    variant_id = models.PositiveIntegerField(help_text="The ID of the variant to play.")
    variant_name = models.CharField(
        max_length=64, help_text="The variant being played as a string."
    )
    num_players = models.PositiveSmallIntegerField(help_text="The number of players.")
    deadline = models.DateTimeField(help_text="The deadline to play this seed.")

    @property
    def seed_name(self) -> str:
        return f"otis{self.pk}"

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.deadline

    class Meta:
        ordering = ("-deadline",)


class HanabiReplay(models.Model):
    contest = models.ForeignKey(HanabiContest, on_delete=models.CASCADE)
    replay_id = models.PositiveIntegerField(
        help_text="The ID of the replay.",
        unique=True,
    )
    game_score = models.PositiveIntegerField(help_text="The game score.")
    turn_count = models.PositiveIntegerField(help_text="The number of turns elapsed.")
    spade_score = models.FloatField(help_text="The number of spades obtained.")


class HanabiParticipation(models.Model):
    player = models.ForeignKey(HanabiPlayer, on_delete=models.CASCADE)
    replay = models.ForeignKey(HanabiReplay, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("player", "replay")
