from django.forms import ModelForm

from .models import ExamAttempt


class ExamAttemptForm(ModelForm):
	class Meta:
		fields = ('guess1', 'guess2', 'guess3', 'guess4', 'guess5')
		model = ExamAttempt
