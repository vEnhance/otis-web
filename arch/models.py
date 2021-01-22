from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse_lazy
import core
import reversion

# Create your models here.

@reversion.register()
class Problem(models.Model):
	source = models.CharField(max_length = 255,
			help_text = r"The source of the problem, such as `TSTST 2020/3`." \
			r"If in doubt on formatting, follow what is written on the handout.",
			blank = True)
	description = models.CharField(max_length = 255,
			help_text = r"A short description of the problem, e.g. `Quirky triangles.`. "\
			r"Most important if the problem does not have a source given. " \
			r"Use sentence case.")
	group = models.ForeignKey(core.models.UnitGroup,
			on_delete = models.CASCADE,
			help_text = "The unit to which this problem belongs.")
	class Meta:
		ordering = ('source', 'description',)
	def __str__(self):
		return str(self.group) + ": " + (self.source or self.description)
	def get_absolute_url(self):
		return reverse_lazy("hint_list", args=(self.id,))

@reversion.register()
class Hint(models.Model):
	problem = models.ForeignKey(Problem,
			on_delete = models.CASCADE,
			help_text = r"The container of the current hint.")
	keywords = models.CharField(max_length = 255, default='', blank=True,
			help_text = r"A comma-separated list of keywords that a solver could look at " \
			"to help them guess whether the hint is relevant or not. " \
			"These are viewable immediately, so no spoilers here.")
	number = models.PositiveIntegerField(
			help_text = r"A number from 0 to 100 used to indicate an " \
			r"ordering for the hints. " \
			r"Here a number 0 means a small nudge given to someone at the very start " \
			r"whereas 100 means a hint given to someone who was read all previous hints " \
			r"or is close to the end of the problem. " \
			r"Do your best to make up an extrapolation for everything in between. " \
			r"A good idea is to give a sequence of hints with nearby numbers, say 20/21/22, " \
			r"each of which elaborates on the previous hint." \
			)
	content = models.TextField(
			help_text = "The content of the hint. LaTeX rendering is okay."
			)
	class Meta:
		ordering = ('number',)
		unique_together = ('problem', 'number',)
	def __str__(self):
		return "Hint %d for %s" %(self.number, self.problem)

	def get_absolute_url(self):
		return reverse_lazy("hint_detail", args=(self.id,))
