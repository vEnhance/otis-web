from django import forms
from . import models

class HintUpdateFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Hint
		fields = ('number', 'keywords', 'content', 'reason',)

class ProblemUpdateFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Problem
		fields = ('source', 'description', 'aops_url', 'reason',)

class ProblemModelChoiceField(forms.ModelChoiceField):
	def label_from_instance(self, obj ):
		assert isinstance(obj, models.Problem)
		return f'[{obj.puid}] {obj.description}'

class ProblemSelectForm(forms.Form):
	lookup_problem = ProblemModelChoiceField(
			to_field_name='puid',
			queryset = models.Problem.objects.all()
			)
