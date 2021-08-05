from django.forms import ModelForm
import exams.models

class ExamAttemptForm(ModelForm):
	fields = ('guess1', 'guess2', 'guess3', 'guess4', 'guess5')
	model = exams.models.ExamAttempt
