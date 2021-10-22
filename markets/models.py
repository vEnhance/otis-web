from core.models import Semester
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.urls.base import reverse_lazy

# Create your models here.


class Market(models.Model):
	start_date = models.DateTimeField(help_text="When the market becomes visible to players")
	end_date = models.DateTimeField(help_text="When the market closes")
	semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
	slug = models.SlugField(help_text="Slug for the market", unique=True)
	title = models.CharField(help_text="Title of the market", max_length=80)
	prompt = models.TextField(help_text="Full text of the question")
	answer = models.FloatField(help_text="The answer to the question")
	weight = models.FloatField(
		help_text="The max score to assign to the market, "
		"used in the scoring function",
		default=2
	)
	alpha = models.FloatField(
		help_text="Exponent corresponding to harshness of the market, "
		"used in the scoring function",
		default=2
	)

	def __str__(self) -> str:
		return f'{self.title} ({self.slug})'

	def get_absolute_url(self) -> str:
		return reverse_lazy('market-results', args=(self.slug, ))


class Guess(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	market = models.ForeignKey(Market, on_delete=models.CASCADE)
	value = models.FloatField(help_text="User's guess", validators=[MinValueValidator(0.000001)])
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

	def get_score(self) -> float:
		a = round(self.market.answer, ndigits=6)
		b = round(self.value, ndigits=6)
		assert a > 0 and b > 0
		return round(self.market.weight * min(a / b, b / a)**self.market.alpha, ndigits=2)

	def set_score(self):
		self.score = self.get_score()
		self.save()

	def get_absolute_url(self) -> str:
		return reverse_lazy('market-results', args=(self.market.slug, ))