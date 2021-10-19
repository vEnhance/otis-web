from core.models import Semester
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models

# Create your models here.


class Market(models.Model):
	start_date = models.DateTimeField(help_text="When the market becomes visible to players")
	end_date = models.DateTimeField(help_text="When the market closes")
	semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
	slug = models.SlugField(help_text="Slug for the market", unique=True)
	title = models.CharField(help_text="Title of the market", max_length=80)
	prompt = models.TextField(help_text="Full text of the question")
	answer = models.FloatField(help_text="The answer to the question")


class Guess(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	market = models.ForeignKey(Market, on_delete=models.CASCADE)
	value = models.FloatField(
		help_text="User's guess",
		validators=[MinValueValidator(0.01, message="Need to enter a number at least 0.01.")]
	)
	score = models.FloatField(help_text="The score for the guess, computed by the backend.")
