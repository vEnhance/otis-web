from django import forms
from django.core.validators import FileExtensionValidator

from dashboard.models import PSet, UploadedFile


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


pset_file_validator = FileExtensionValidator(
	allowed_extensions=['pdf', 'txt', 'tex', 'png', 'jpg']
)


class PSetSubmitForm(forms.ModelForm):
	content = forms.FileField(
		help_text="The file itself",
		validators=[
			pset_file_validator,
		],
	)

	class Meta:
		model = PSet
		fields = (
			'unit',
			'clubs',
			'hours',
			'feedback',
			'special_notes',
			'next_unit_to_unlock',
		)


class PSetResubmitForm(forms.ModelForm):
	content = forms.FileField(
		help_text="The file itself",
		validators=[
			pset_file_validator,
		],
	)

	class Meta:
		model = PSet
		fields = (
			'clubs',
			'hours',
			'feedback',
			'special_notes',
			'next_unit_to_unlock',
		)


class DiamondsForm(forms.Form):
	code = forms.CharField(label="", max_length=64, required=True)
