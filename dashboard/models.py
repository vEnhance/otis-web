# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import os

from django.contrib.auth import models as auth
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse_lazy

import core.models
import roster.models


def content_file_name(instance, filename):
	now = datetime.datetime.now()
	return os.path.join(instance.category, instance.owner.username,\
			now.strftime("%Y-%m-%d-%H%M%S"), filename)

class UploadedFile(models.Model):
	"""An uploaded file, for example a transcript or homework solutions."""
	CHOICES = (("psets", "PSet Submission"), ("scripts", "Transcript"),
			("notes", "Notes / Comments"), ("misc", "Miscellaneous"))
	benefactor = models.ForeignKey(roster.models.Student,
			on_delete = models.CASCADE,
			help_text = "The student for which this file is meant")
	owner = models.ForeignKey(auth.User,
			on_delete = models.CASCADE,
			help_text = "The user who uploaded the file")
	category = models.CharField(max_length = 10, choices = CHOICES,
			help_text = "What kind of file this is")
	description = models.CharField(max_length = 250, blank = True,
			help_text = "Optional description of the file")
	content = models.FileField(help_text = "The file itself",
			upload_to = content_file_name,
			validators = [FileExtensionValidator(
				allowed_extensions=['pdf','txt','tex','png','jpg'])])
	unit = models.ForeignKey(core.models.Unit, null = True, blank = True,
			on_delete = models.SET_NULL,
			help_text = "The unit for which this file is associated")
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
		ordering = ('-created_at',)

def download_file_name(instance, filename):
	return os.path.join("global", str(instance.semester.id), filename)
def get_absolute_url(self):
	return self.url

class SemesterDownloadFile(models.Model):
	semester = models.ForeignKey(core.models.Semester,
			on_delete = models.CASCADE,
			help_text = "The semester to which the file is associated")
	description = models.CharField(max_length = 250, blank = True,
			help_text = "Optional description of the file")
	content = models.FileField(help_text = "The file itself",
			upload_to = download_file_name,
			validators = [FileExtensionValidator(
				allowed_extensions=['pdf','txt','tex','png','jpg'])])
	created_at = models.DateTimeField(auto_now_add=True)
	def __str__(self):
		return os.path.basename(self.content.name)
	class Meta:
		ordering = ('-created_at',)
	def get_absolute_url(self):
		return self.content.url

class PSet(models.Model):
	approved = models.BooleanField(
			help_text = "Whether the problem set has been checked off",
			default = False)
	student = models.ForeignKey(roster.models.Student,
			help_text = "The student attached to this",
			on_delete = models.CASCADE)
	unit = models.ForeignKey(core.models.Unit,
			help_text = "The unit you want to submit for",
			on_delete = models.SET_NULL,
			null = True,
			)
	upload = models.ForeignKey(UploadedFile,
			help_text = "The associated upload file for this problem set",
			on_delete = models.CASCADE,
			)
	hours = models.FloatField(
			help_text = "Number of hours spent on this problem set",
			verbose_name = "Hours spent (estimate)",
			null = True, blank = True,
			)
	clubs = models.IntegerField(
			help_text = "Total number of clubs that you solved (including 1♣ if feedback written)",
			verbose_name = "Total ♣ earned",
			null = True, blank = True,
			)
	eligible = models.BooleanField(default = True,
			help_text = "Whether to count this for leveling up")
	feedback = models.TextField(
			verbose_name = "Feedback on problem set, worth [1♣]",
			help_text = "Any other feedback about the problem set",
			blank = True)
	next_unit_to_unlock = models.ForeignKey(core.models.Unit,
			help_text = "The unit you want to work on next (leave blank for any)",
			on_delete = models.SET_NULL,
			null = True, blank = True,
			related_name = 'unblocking_psets',
			)
	special_notes = models.TextField(
			help_text = "If there's anything you need to say before we proceed",
			blank = True)
	instructor_comments = models.TextField(
			help_text = "Any comment from the instructor about the submission",
			blank = True)
	def __str__(self):
		return f'{self.student.name} submits {self.unit}'
	def get_absolute_url(self):
		return reverse_lazy('pset', args=(self.pk,))

class ProblemSuggestion(models.Model):
	student = models.ForeignKey(roster.models.Student,
			on_delete = models.CASCADE,
			help_text = "Student who suggested the problem.")
	unit = models.ForeignKey(core.models.Unit,
			on_delete = models.CASCADE,
			help_text = "The unit to suggest the problem for.")
	weight = models.PositiveSmallIntegerField(
			choices = ((2,2), (3,3), (5,5), (9,9)),
			null = True, blank = True)
	source = models.CharField(max_length = 60,
			help_text = "Source of the problem, e.g. `Shortlist 2018 A7`.")
	description = models.CharField(max_length = 100,
			help_text = "A one-line summary of problem, e.g. `Inequality with cube roots`.")
	statement = models.TextField(help_text = "Statement of the problem, in LaTeX.")
	solution = models.TextField(help_text = "Solution to the problem, in LaTeX.")
	comments = models.TextField(help_text = "Any extra comments.", blank=True)
	acknowledge = models.BooleanField(help_text = \
			"Acknowledge me for this contribution. "
			"(Uncheck for an anonymous contribution.)", default=True)

	resolved = models.BooleanField(default = False,
			help_text = "Whether staff has processed this.")
	reason = models.TextField(blank = True,
			help_text = "Staff notes on reviewing.")
	created_at = models.DateTimeField(auto_now_add = True)
	notified = models.BooleanField(default = False,
			help_text = "Whether student has received the staff's comments.")

	def __str__(self):
		return self.student.name + " suggested " + self.source \
				+ " for " + str(self.unit.group)

def achievement_image_file_name(instance, filename):
	return os.path.join('badges', instance.code + '_' + filename)

class Achievement(models.Model):
	code = models.CharField(max_length = 96, unique = True)
	name = models.CharField(max_length = 128,
			help_text = "Name of the achievement")
	image = models.FileField(upload_to = achievement_image_file_name,
			help_text = "Image for the obtained badge", null = True, blank = True)
	description = models.TextField(help_text = "How to obtain this achievement")
	active = models.BooleanField(
			help_text = "Whether the code is active right now", default = True)
	diamonds = models.PositiveSmallIntegerField(default = 1,
			help_text = "Amount of diamonds for this achievement")
	def __str__(self):
		return self.name

class Level(models.Model):
	threshold = models.IntegerField(unique = True,
			help_text = "The number of the level")
	name = models.CharField(max_length = 128, unique = True,
			help_text = "The name of the level")
	def __str__(self):
		return f'Level {{number}}: {{name}}'

