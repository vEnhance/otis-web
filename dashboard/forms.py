from django import forms
from django.core.validators import FileExtensionValidator

import dashboard.models


class NewUploadForm(forms.ModelForm):
	class Meta:
		model = dashboard.models.UploadedFile
		fields = ('category', 'content', 'description')
		widgets = {
			'description': forms.Textarea(
				attrs = {'cols': 40, 'rows': 2}),
		}
		help_texts = {
			'content' : "",
		}

class ResolveSuggestionForm(forms.ModelForm):
	class Meta:
		model = dashboard.models.ProblemSuggestion
		fields = ('reason',)
		widgets = {'reason' : forms.Textarea(attrs = {'cols':  30, 'rows' : 4}), }
		help_texts = { 'reason' : '' }

class PSetForm(forms.ModelForm):
	content = forms.FileField(help_text = "The file itself",
			validators = [FileExtensionValidator(
				allowed_extensions=['pdf','txt','tex','png','jpg'])])
	class Meta:
		model = dashboard.models.PSet
		fields = ('unit', 'hours', 'feedback', 'clubs',
				'next_unit_to_unlock', 'special_notes',)

class DiamondsForm(forms.Form):
	code = forms.CharField(label = "", max_length = 64, required = True)
