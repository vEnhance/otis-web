from django import forms
import dashboard

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
