from django import forms

from .models import Hint, Problem


class HintUpdateFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text="Reason for editing.", required=False)

	class Meta:
		model = Hint
		fields = (
			'problem',
			'number',
			'keywords',
			'content',
			'reason',
		)


class ProblemUpdateForm(forms.ModelForm):
	class Meta:
		model = Problem
		fields = ('puid', )


class ProblemSelectForm(forms.Form):
	problem = forms.ModelChoiceField(queryset=Problem.objects.all())
