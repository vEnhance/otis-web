from datetime import timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query import QuerySet
from django.urls.base import reverse
from django.utils import timezone
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD

from core.models import Semester

# Create your models here.


class StartedMarketManager(models.Manager):
    def get_queryset(self) -> QuerySet["Market"]:
        now = timezone.now()
        return super().get_queryset().filter(start_date__lte=now)


class ActiveMarketManager(models.Manager):
    def get_queryset(self) -> QuerySet["Market"]:
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .filter(
                start_date__lte=now,
                end_date__gte=now,
            )
        )


class UpcomingMarketManager(models.Manager):
    def get_queryset(self) -> QuerySet["Market"]:
        now = timezone.now()
        return super().get_queryset().filter(start_date__lte=now + timedelta(days=4))


class Market(models.Model):
    start_date = models.DateTimeField(
        help_text="When the market becomes visible to players"
    )
    end_date = models.DateTimeField(help_text="When the market closes")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    slug = models.SlugField(help_text="Slug for the market", unique=True)
    title = models.CharField(help_text="Title of the market", max_length=80)

    prompt = MarkdownField(
        rendered_field="prompt_rendered",
        help_text="Full text of the question",
        validator=VALIDATOR_STANDARD,
    )
    prompt_rendered = RenderedMarkdownField()
    solution = MarkdownField(
        rendered_field="solution_rendered",
        help_text="Comments that appear in the market results.",
        validator=VALIDATOR_STANDARD,
        blank=True,
    )
    solution_rendered = RenderedMarkdownField()

    answer = models.FloatField(
        help_text="The answer to the question", blank=True, null=True
    )
    weight = models.FloatField(
        help_text="The max score to assign to the market, used in the scoring function",
        default=4,
    )
    alpha = models.FloatField(
        help_text="Exponent corresponding to harshness of the market, "
        "used in the scoring function; leave blank for special scoring.",
        default=2,
        null=True,
        blank=True,
    )
    show_answer = models.BooleanField(default=True)
    show_results = models.BooleanField(default=True)
    int_guesses_only = models.BooleanField(
        help_text="Only allow integer guesses for this market.", default=False
    )

    objects = models.Manager()
    started = StartedMarketManager()
    active = ActiveMarketManager()
    upcoming = UpcomingMarketManager()

    class Meta:
        ordering = ("-end_date",)

    def __str__(self) -> str:
        return f"{self.title} ({self.slug})"

    def get_absolute_url(self) -> str:
        if self.has_ended or not self.has_started:
            return reverse("market-results", args=(self.slug,))
        else:
            return reverse("market-guess", args=(self.slug,))

    def clean(self):
        super().clean()
        if (
            self.int_guesses_only is True
            and self.answer is not None
            and not self.answer.is_integer()
        ):
            raise ValidationError({"answer": "This market is integer-valued."})

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start_date

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.end_date

    @property
    def is_upcoming(self) -> bool:
        return timezone.now() < self.start_date < timezone.now() + timedelta(days=4)

    @property
    def pretty_answer(self) -> None | float | int:
        if self.answer is None:
            return None
        elif self.int_guesses_only:
            return int(self.answer)
        else:
            return self.answer


class Guess(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    value = models.FloatField(
        help_text="User's guess",
        validators=[
            MinValueValidator(0.000001),
            MaxValueValidator(1000000),
        ],
    )
    score = models.FloatField(
        help_text="The score for the guess, computed by the backend.",
        null=True,
        blank=True,
    )
    public = models.BooleanField(
        default=False,
        help_text="If checked, will display your name "
        "next to your guess in the statistics, for bragging rights. "
        "By default, this is off and your guess is recorded anonymously.",
    )

    class Meta:
        unique_together = (
            "user",
            "market",
        )
        verbose_name_plural = "Guesses"

    def __str__(self) -> str:
        return f"Guessed {self.value} at {self.created_at}"

    def get_absolute_url(self) -> str:
        return reverse("market-results", args=(self.market.slug,))

    def clean(self):
        super().clean()
        if self.market.int_guesses_only is True and not self.value.is_integer():
            raise ValidationError({"value": "This market only allows integer guesses."})

    def get_score(self) -> Optional[float]:
        if self.market.answer is None or self.market.alpha is None:
            return None
        a = round(self.market.answer, ndigits=6)
        b = round(self.value, ndigits=6)
        assert a > 0 and b > 0
        return round(
            self.market.weight * min(a / b, b / a) ** self.market.alpha, ndigits=2
        )

    def set_score(self):
        score = self.get_score()
        if score is not None:
            self.score = score
            self.save()

    @property
    def pretty_value(self) -> float | int:
        if self.market.int_guesses_only:
            return int(self.value)
        else:
            return self.value

    @property
    def results_value(self) -> str:
        if self.market.int_guesses_only:
            return f"{int(self.value):d}"
        else:
            return f"{self.value:.6f}"
