from django.db import models
import core

# Create your models here.

class Hint(models.Model):
	problem_source = models.CharField(max_length = 255,
			help_text = r"The source of the problem, such as `TSTST 2020/3`." \
			r"If in doubt on formatting, follow what is written on the handout." \
			r"If the problem does not include a source, do your best" \
			r"to write a two or three word description of the problem" \
			r"that can be recognized, like `100 sleepy students` or `sloth blocking ruler`.")

	group = models.ForeignKey(core.models.UnitGroup,
			on_delete = models.CASCADE,
			help_text = "The unit to which this problem belongs.")

	keywords = models.CharField(max_length = 255, default='', blank=False,
			help_text = r"A list of keywords that a solver could look at " \
			"to help them guess whether the hint is relevant or not. " \
			"These are viewable immediately, so no spoilers here.")

	numbers = models.PositiveIntegerField(
			help_text = r"A number from 0 to 100 used to indicate an " \
			r"ordering for the hints." \
			r"Here a number 0 means a small nudge given to someone at the very start " \
			r"whereas 100 means a hint given to someone who was read all previous hints " \
			r"or is close to the end of the problem." \
			r"Do your best to make up an extrapolation for everything in between. " \
			r"A good idea is to give a sequence of hints with nearby numbers, say 20/21/22, " \
			r"each of which elaborates on the previous hint." \
			)

	content = models.TextField(
			help_text = "The content of the hint. LaTeX rendering is okay."
			)

