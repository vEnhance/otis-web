from django.core.validators import FileExtensionValidator
from django import forms
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
	# TODO: restrict to units where the student
	# has not already submitted a problem set
	# TODO move content to first field
	# TODO change widgets
