# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import core.models
import roster.models
import datetime
from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth import models as auth
from django.forms import ValidationError

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
	now = datetime.datetime.now()
	return os.path.join("global", str(instance.semester.id), filename)

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
	resolved = models.BooleanField(help_text = "Whether staff has processed this.", default=False)
	review_notes = models.TextField(help_text = "Staff notes on reviewing.", blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
