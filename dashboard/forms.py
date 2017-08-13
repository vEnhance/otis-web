from django import forms
import dashboard

class NewUploadForm(forms.ModelForm):
	class Meta:
		model = dashboard.models.UploadedFile
		fields = ('file_type', 'file_content', 'description', 'unit')
		widgets = {
			'description': forms.Textarea(attrs={'cols': 40, 'rows': 3}),
		}
		help_texts = {
			'file_content' : "",
			'description': ""
		}
