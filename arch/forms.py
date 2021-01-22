from django import forms
from . import models

class HintFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Hint
		fields = ('keywords', 'number', 'content', 'reason',)

class ProblemFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Problem
		fields = ('source', 'description', 'group',)
