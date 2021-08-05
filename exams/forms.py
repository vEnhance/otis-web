from django.forms import ModelForm

import exams.models


class ExamAttemptForm(ModelForm):
	class Meta:
		fields = ('guess1', 'guess2', 'guess3', 'guess4', 'guess5')
		model = exams.models.ExamAttempt
