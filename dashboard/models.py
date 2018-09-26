# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import core.models
import roster.models
import datetime
from django.db import models
from django.contrib.auth import models as auth
from django.forms import ValidationError

def content_file_name(instance, filename):
	now = datetime.datetime.now()
	return os.path.join(instance.category, instance.owner.username,\
			now.strftime("%Y-%m"), filename)

ALLOWED_UPLOAD_TYPES = (
		'application/pdf',
		'application/x-latex',
		'text/x-tex',
		'text/plain',
		)

def validate_file_extension(value):
	content_type = value.file.content_type
	if not content_type.startswith('text/') and content_type not in ALLOWED_UPLOAD_TYPES:
		raise ValidationError("File type not accepted: " \
				"must be PDF or plain TeX/text, "
				"but got MIME-type " + content_type)

class UploadedFile(models.Model):
	"""An uploaded file, for example a transcript or homework solutions."""
	CHOICES = (("psets", "PSet Submission"), ("scripts", "Transcript"),
			("notes", "Notes / Comments"), ("misc", "Miscellaneous"))
	benefactor = models.ForeignKey(roster.models.Student,
			help_text = "The student for which this file is meant")
	owner = models.ForeignKey(auth.User,
			help_text = "The user who uploaded the file")
	category = models.CharField(max_length = 10, choices = CHOICES,
			help_text = "What kind of file this is")
	description = models.CharField(max_length = 250, blank = True,
			help_text = "Optional description of the file")
	content = models.FileField(help_text = "The file itself",
			upload_to = content_file_name,
			validators = [validate_file_extension])
	unit = models.ForeignKey(core.models.Unit, null = True, blank = True,
			help_text = "The unit for which this file is associated")
	created_at = models.DateTimeField(auto_now_add=True)
	def __str__(self):
		return os.path.basename(self.content.name)
	class Meta:
		ordering = ('-created_at',)

# Create your models here.
