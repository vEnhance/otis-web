from typing import Optional

from core.models import Semester
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query import QuerySet
from django.urls.base import reverse_lazy
from django.utils import timezone

# Create your models here.


class StartedMarketManager(models.Manager):
	def get_queryset(self) -> QuerySet['Market']:
		now = timezone.now()
		return super().get_queryset().filter(start_date__lte=now)


class ActiveMarketManager(models.Manager):
	def get_queryset(self) -> QuerySet['Market']:
		now = timezone.now()
		return super().get_queryset().filter(
			start_date__lte=now,
			end_date__gte=now,
		)


class Market(models.Model):
	start_date = models.DateTimeField(help_text="When the market becomes visible to players")
	end_date = models.DateTimeField(help_text="When the market closes")
	semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
	slug = models.SlugField(help_text="Slug for the market", unique=True)
	title = models.CharField(help_text="Title of the market", max_length=80)
	prompt = models.TextField(help_text="Full text of the question")
	solution = models.TextField(
		help_text="Comments that appear in the market results.", blank=True
	)
	answer = models.FloatField(help_text="The answer to the question", blank=True, null=True)
	weight = models.FloatField(
		help_text="The max score to assign to the market, "
		"used in the scoring function",
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

	objects = models.Manager()
	started = StartedMarketManager()
	active = ActiveMarketManager()

	def __str__(self) -> str:
		return f'{self.title} ({self.slug})'

	def get_absolute_url(self) -> str:
		if self.has_ended or not self.has_started:
			return reverse_lazy('market-results', args=(self.slug, ))
		else:
			return reverse_lazy('market-guess', args=(self.slug, ))

	@property
	def has_started(self) -> bool:
		return timezone.now() >= self.start_date

	@property
	def has_ended(self) -> bool:
		return timezone.now() >= self.end_date

	class Meta:
		ordering = ('-end_date', )


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
		"By default, this is off and your guess is recorded anonymously."
	)

	class Meta:
		unique_together = (
			'user',
			'market',
		)
		verbose_name_plural = "Guesses"

	def __str__(self) -> str:
		return f"Guessed {self.value} at {self.created_at}"

	def get_score(self) -> Optional[float]:
		if self.market.answer is not None and self.market.alpha is not None:
			a = round(self.market.answer, ndigits=6)
			b = round(self.value, ndigits=6)
			assert a > 0 and b > 0
			return round(self.market.weight * min(a / b, b / a)**self.market.alpha, ndigits=2)
		else:
			return None

	def set_score(self):
		score = self.get_score()
		if score is not None:
			self.score = score
			self.save()

	def get_absolute_url(self) -> str:
		return reverse_lazy('market-results', args=(self.market.slug, ))
