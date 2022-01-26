from pathlib import Path
from typing import Optional

import reversion
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse_lazy


# Create your models here.
@reversion.register()
class Problem(models.Model):
	id = models.AutoField(primary_key=True)
	puid = models.CharField(
		max_length=24,
		help_text="Unique problem identifier, as printed in OTIS handout.",
		unique=True,
		verbose_name="PUID",
		validators=[
			RegexValidator(
				regex=r'^[A-Z0-9]+$', message="Only uppercase letters and digits appear in PUID's."
			)
		],
	)

	def __str__(self) -> str:
		return self.puid

	def get_absolute_url(self):
		return reverse_lazy("hint-list", args=(self.puid, ))

	def get_statement(self) -> Optional[str]:
		if settings.PATH_STATEMENT_ON_DISK is None:
			return None
		statement_path = Path(settings.PATH_STATEMENT_ON_DISK) / (self.puid + '.html')
		if statement_path.exists() and statement_path.is_file():
			return statement_path.read_text()
		return None

	class Meta:
		ordering = ('puid', )


@reversion.register()
class Hint(models.Model):
	id = models.AutoField(primary_key=True)
	problem = models.ForeignKey(
		Problem, on_delete=models.CASCADE, help_text=r"The container of the current hint."
	)
	keywords = models.CharField(
		max_length=255,
		default='',
		blank=True,
		help_text=r"A comma-separated list of keywords that a solver could look at "
		"to help them guess whether the hint is relevant or not. "
		"These are viewable immediately, so no spoilers here. "
		"Examples are 'setup', 'advice', 'answer confirmation', 'nudge',"
		"'main idea', 'solution set', 'converse direction', 'construction', etc. "
		"Not all hints go well with keywords, so you can leave this "
		"blank if you can't think of anything useful to write."
	)
	number = models.PositiveIntegerField(
		help_text=r"A number from 0 to 100 used to indicate an "
		r"ordering for the hints. "
		r"Here a number 0 means a hint given to someone at the very start "
		r"whereas 100 means a hint given to someone who was read all previous hints "
		r"or is close to the end of the problem. "
		r"Do your best to make up an extrapolation for everything in between. "
		r"A good idea is to give a sequence of hints with nearby numbers, say 20/21/22, "
		r"each of which elaborates on the previous hint."
	)
	content = models.TextField(help_text="The content of the hint. LaTeX rendering is okay.")

	class Meta:
		unique_together = (
			'problem',
			'number',
		)

	def __str__(self):
		return f"Hint {self.number}% for {self.problem}"

	def puid(self) -> str:
		return self.problem.puid

	def get_absolute_url(self):
		return reverse_lazy(
			"hint-detail", args=(
				self.problem.puid,
				self.number,
			)
		)
