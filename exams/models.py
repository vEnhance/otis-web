from __future__ import unicode_literals

import core
from django.db import models

# Create your models here.

class MockOlympiad(models.Model):
	CHOICES = ((_, _) for _ in ("Waltz", "Tango", "Foxtrot"))
	family = models.CharField(max_length = 10, choices = CHOICES,
			help_text = "The family that the mock olympiad comes from")
	number = models.PositiveSmallIntegerField(
			help_text = "The number of the test (e.g. Waltz 8)")
	jmo_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the JMO problems")
	usamo_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the USAMO problems")
	solns_url = models.CharField(max_length = 120, blank = True,
			help_text = "The URL to the solutions")

class Assignment(models.Model):
	semester = models.ForeignKey(core.models.Semester,
			help_text = "The semester that the assignment is given in")
	name = models.CharField(max_length = 80, blank = True, unique = True,
			help_text = "Name of the assignment; leave blank for mock olympiads")
	olympiad = models.ForeignKey(MockOlympiad, null = True, blank = True,
			help_text = "If applicable, a PDF of the suitable mock olympiad")
