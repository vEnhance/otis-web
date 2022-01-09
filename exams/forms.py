from django import forms
from django.core.validators import RegexValidator
from django.forms import ModelForm

from .models import ExamAttempt, Feedback, PracticeExam


class ExamAttemptForm(ModelForm[ExamAttempt]):
	class Meta:
		fields = ('guess1', 'guess2', 'guess3', 'guess4', 'guess5')
		model = ExamAttempt


class ParticipationPointsForm(forms.Form):
	exam = forms.ModelChoiceField(PracticeExam.objects.filter(is_test=True))
	pks = forms.CharField(
		widget=forms.Textarea,
		help_text="ID's to create stuff for, paste one per line",
		validators=[
			RegexValidator(r'[0-9\n]+'),
		],
	)
