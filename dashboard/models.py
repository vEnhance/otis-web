# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime
import os
from hashlib import sha256

from core.models import Semester, Unit, UnitGroup
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator, RegexValidator  # NOQA
from django.db import models
from django.urls import reverse_lazy
from roster.models import Student


def validate_at_most_1mb(f: File):  # type: ignore
	if f.size > 1024 * 1024:
		raise ValidationError("At most 1MB allowed")


def content_file_name(instance: 'UploadedFile', filename: str) -> str:
	now = datetime.datetime.now()
	return os.path.join(
		instance.category, instance.owner.username, now.strftime("%Y-%m-%d-%H%M%S"), filename
	)


class UploadedFile(models.Model):
	"""An uploaded file, for example a transcript or homework solutions."""
	CHOICES = (
		("psets", "PSet Submission"), ("scripts", "Transcript"), ("notes", "Notes / Comments"),
		("misc", "Miscellaneous")
	)
	benefactor = models.ForeignKey(
		Student, on_delete=models.CASCADE, help_text="The student for which this file is meant"
	)
	owner = models.ForeignKey(
		User, on_delete=models.CASCADE, help_text="The user who uploaded the file"
	)
	category = models.CharField(
		max_length=10, choices=CHOICES, help_text="What kind of file this is"
	)
	description = models.CharField(
		max_length=250, blank=True, help_text="Optional description of the file"
	)
	content = models.FileField(
		help_text="The file itself",
		upload_to=content_file_name,
		validators=[FileExtensionValidator(allowed_extensions=['pdf', 'txt', 'tex', 'png', 'jpg'])]
	)
	unit = models.ForeignKey(
		Unit,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		help_text="The unit for which this file is associated"
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.filename

	@property
	def filename(self):
		return os.path.basename(self.content.name)

	@property
	def url(self):
		return self.content.url

	class Meta:
		ordering = ('-created_at', )

	def get_absolute_url(self):
		return self.url


def download_file_name(instance: 'SemesterDownloadFile', filename: str) -> str:
	return os.path.join("global", str(instance.semester.id), filename)


class SemesterDownloadFile(models.Model):
	semester = models.ForeignKey(
		Semester,
		on_delete=models.CASCADE,
		help_text="The semester to which the file is associated"
	)
	description = models.CharField(
		max_length=250, blank=True, help_text="Optional description of the file"
	)
	content = models.FileField(
		help_text="The file itself",
		upload_to=download_file_name,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return os.path.basename(self.content.name)

	class Meta:
		ordering = ('-created_at', )

	def get_absolute_url(self):
		return self.content.url


class PSet(models.Model):
	resubmitted = models.BooleanField(
		help_text="Tracks if problem set resubmitted", default=False
	)
	approved = models.BooleanField(
		help_text="Whether the latest version of the problem set has been checked off",
		default=False
	)
	student = models.ForeignKey(
		Student, help_text="The student attached to this", on_delete=models.CASCADE
	)
	unit = models.ForeignKey(
		Unit,
		help_text="The unit you want to submit for",
		on_delete=models.SET_NULL,
		null=True,
	)
	upload = models.ForeignKey(
		UploadedFile,
		help_text="The associated upload file for this problem set",
		on_delete=models.CASCADE,
		null=True,
		blank=False,
	)
	hours = models.FloatField(
		help_text="Number of hours spent on this problem set",
		verbose_name="Hours spent (estimate)",
		null=True,
		blank=True,
		validators=[
			MinValueValidator(0),
			MaxValueValidator(200),
		],
	)
	clubs = models.IntegerField(
		help_text="Total number of clubs that you solved (including 1♣ if feedback written)",
		verbose_name="Total ♣ earned",
		null=True,
		blank=True,
		validators=[
			MinValueValidator(0),
			MaxValueValidator(200),
		]
	)
	eligible = models.BooleanField(
		default=True, help_text="Whether to count this for leveling up"
	)
	rejected = models.BooleanField(
		default=False, help_text="If a problem set is rejected and needs attention."
	)
	feedback = models.TextField(
		verbose_name="Feedback on problem set, worth [1♣]",
		help_text="Any other feedback about the problem set",
		blank=True
	)
	next_unit_to_unlock = models.ForeignKey(
		Unit,
		help_text="The unit you want to work on next (leave blank for none)",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='unblocking_psets',
	)
	special_notes = models.TextField(
		help_text="If there's anything you need to say before we proceed", blank=True
	)

	def __str__(self):
		return f'{self.student.name} submits {self.unit}'

	def get_absolute_url(self):
		return reverse_lazy('pset', args=(self.pk, ))

	class Meta:
		verbose_name = "PSet submission"
		verbose_name_plural = "PSet submissions"


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

	def __str__(self) -> str:
		return f"{self.user.username} suggested {self.source} for {self.unit.group}"


def achievement_image_file_name(instance: 'Achievement', filename: str) -> str:
	kludge = (settings.SECRET_KEY or '') + '_otis_' + str(instance.pk)
	h = sha256(kludge.encode('ascii')).hexdigest()[0:18]
	return os.path.join('badges', h + os.path.splitext(filename)[-1])


class Achievement(models.Model):
	code = models.CharField(
		max_length=96,
		unique=True,
		null=True,
		validators=[
			RegexValidator(regex=r'^[a-f0-9]{24,25}$', message='24-25 char hex string'),
		],
	)  # e.g. 52656164546865436f646521
	name = models.CharField(max_length=128, help_text="Name of the achievement")
	image = models.ImageField(
		upload_to=achievement_image_file_name,
		help_text="Image for the obtained achievement, at most 1MB.",
		null=True,
		blank=True,
		validators=[validate_at_most_1mb],
	)
	description = models.TextField(
		help_text="Text shown beneath this achievement for students who obtain it."
	)
	solution = models.TextField(help_text="Internal note by Evan where the diamond is hidden")
	active = models.BooleanField(help_text="Whether the code is active right now", default=True)
	diamonds = models.SmallIntegerField(
		default=1, help_text="Number of diamonds for this achievement"
	)
	creator = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		help_text="User who owns this achievement"
	)

	def __str__(self) -> str:
		return str(self.name)


class Level(models.Model):
	threshold = models.IntegerField(unique=True, help_text="The number of the level")
	name = models.CharField(max_length=128, help_text="The name of the level")

	def __str__(self):
		return f'Level {self.threshold}: {self.name}'


class AchievementUnlock(models.Model):
	user = models.ForeignKey(
		User, on_delete=models.CASCADE, help_text="The user who unlocked the achievement"
	)
	achievement = models.ForeignKey(
		Achievement, on_delete=models.CASCADE, help_text="The achievement that was obtained"
	)
	timestamp = models.DateTimeField(
		auto_now_add=True, help_text='The time the achievement was granted'
	)

	def __str__(self) -> str:
		return self.timestamp.strftime('%c')

	class Meta:
		unique_together = (
			'user',
			'achievement',
		)


class QuestComplete(models.Model):
	student = models.ForeignKey(
		Student, on_delete=models.CASCADE, help_text="Student obtaining this reward"
	)
	title = models.CharField(max_length=160, help_text="A summary")
	spades = models.PositiveSmallIntegerField(help_text="The number of spades granted")
	timestamp = models.DateTimeField(
		auto_now_add=True, help_text='The time the achievement was granted'
	)

	CATEGORY_CHOICES = (
		("PR", "Pull request"),
		("BR", "Bug report"),
		("WK", "Wiki bonus"),
		("US", "USEMO Score"),
		("UG", "USEMO Grading"),
		("MS", "Miscellaneous"),
	)
	category = models.CharField(
		max_length=4,
		choices=CATEGORY_CHOICES,
		default="MS",
	)

	def __str__(self) -> str:
		return self.title + ' ' + self.timestamp.strftime('%c')


class BonusLevel(models.Model):
	group = models.OneToOneField(UnitGroup, on_delete=models.CASCADE)
	level = models.PositiveSmallIntegerField(help_text="Level to spawn at")
	active = models.BooleanField(default=True)

	def __str__(self) -> str:
		return f"Lv. {self.level} Bonus ({'active' if self.active else 'inert'})"


class BonusLevelUnlock(models.Model):
	timestamp = models.DateTimeField(auto_now_add=True)
	student = models.ForeignKey(Student, on_delete=models.CASCADE)
	bonus = models.ForeignKey(BonusLevel, on_delete=models.CASCADE)

	def __str__(self) -> str:
		return self.timestamp.isoformat()


def palace_image_file_name(instance: 'PalaceCarving', filename: str) -> str:
	return os.path.join('palace', filename)


class PalaceCarving(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
	display_name = models.CharField(
		max_length=128,
		help_text="How you would like your name to be displayed in the Ruby Palace."
	)
	message = models.TextField(
		max_length=1024, help_text="You can write a message here", blank=True
	)
	hyperlink = models.URLField(help_text="An external link of your choice", blank=True)
	visible = models.BooleanField(
		help_text="Uncheck to hide your carving altogether (can change your mind later)",
		default=True
	)
	created_at = models.DateTimeField(auto_now_add=True)
	image = models.ImageField(
		upload_to=palace_image_file_name,
		help_text=
		"Optional small photo that will appear next to your carving, no more than 1 megabyte",
		null=True,
		blank=True,
		validators=[validate_at_most_1mb],
	)

	def __str__(self) -> str:
		return f"Palace carving for {self.display_name}"
