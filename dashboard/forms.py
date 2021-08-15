from django import forms
from django.core.validators import FileExtensionValidator

from dashboard.models import ProblemSuggestion, PSet, UploadedFile


class NewUploadForm(forms.ModelForm):

	class Meta:
		model = UploadedFile
		fields = ('category', 'content', 'description')
		widgets = {
			'description': forms.Textarea(attrs={
				'cols': 40,
				'rows': 2
			}),
		}
		help_texts = {
			'content': "",
		}


class ResolveSuggestionForm(forms.ModelForm):

	class Meta:
		model = ProblemSuggestion
		fields = ('reason',)
		widgets = {
			'reason': forms.Textarea(attrs={
				'cols': 30,
				'rows': 4
			}),
		}
		help_texts = {'reason': ''}


class PSetForm(forms.ModelForm):
	content = forms.FileField(
		help_text="The file itself",
		validators=[
			FileExtensionValidator(
				allowed_extensions=['pdf', 'txt', 'tex', 'png', 'jpg'])
		])

	class Meta:
		model = PSet
		fields = (
			'unit',
			'hours',
			'feedback',
			'clubs',
			'next_unit_to_unlock',
			'special_notes',
		)


class DiamondsForm(forms.Form):
	code = forms.CharField(label="", max_length=64, required=True)
