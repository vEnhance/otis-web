# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import core.models
import roster.models
from django.db import models
from django.contrib.auth import models as auth

class UploadedFile(models.Model):
	"""An uploaded file, for example a transcript or homework solutions."""
	CHOICES = (("HMWK", "Homework"), ("TRNS", "Transcript"),
			("NOTE", "Notes / Comments"), ("MISC", "Miscellaneous"))
	benefactor = models.ForeignKey(roster.models.Student,
			help_text = "The student for which this file is meant")
	owner = models.ForeignKey(auth.User,
			help_text = "The user who uploaded the file")
	file_type = models.CharField(max_length = 10, choices = CHOICES,
			help_text = "What kind of file this is")
	content = models.FileField(help_text = "The file itself")
	description = models.CharField(max_length = 160, blank = True,
			help_text = "A description of the file (defaults to filename if blank)")
	unit = models.ForeignKey(core.models.Unit, null = True, blank = True,
			help_text = "The unit for which this file is associated")

# Create your models here.
