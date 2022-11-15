from core.models import Unit
from django.contrib.auth.models import User
from django.db import models


class ProblemSuggestion(models.Model):
	user = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		help_text="User who suggested the problem.",
	)
	unit = models.ForeignKey(
		Unit, on_delete=models.CASCADE, help_text="The unit to suggest the problem for."
	)
	weight = models.PositiveSmallIntegerField(
		choices=((2, 2), (3, 3), (5, 5), (9, 9)), null=True, blank=True
	)
	source = models.CharField(
		max_length=60, help_text="Source of the problem, e.g. `Shortlist 2018 A7`."
	)
	description = models.CharField(
		max_length=100,
		help_text="A one-line summary of problem, e.g. `Inequality with cube roots`."
	)
	statement = models.TextField(help_text="Statement of the problem, in LaTeX.")
	solution = models.TextField(help_text="Solution to the problem, in LaTeX.")
	comments = models.TextField(help_text="Any extra comments.", blank=True)
	acknowledge = models.BooleanField(
		help_text="Acknowledge me for this contribution. "
		"(Uncheck for an anonymous contribution.)",
		default=True
	)

	resolved = models.BooleanField(default=False, help_text="Whether staff has processed this.")
	eligible = models.BooleanField(
		default=True, help_text="Whether this suggestion is eligible for spades."
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'dashboard_problemsuggestion'  # historical babbage

	def __str__(self) -> str:
		return f"{self.user.username} suggested {self.source} for {self.unit.group}"
