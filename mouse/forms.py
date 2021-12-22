from django import forms


class ScoreForm(forms.Form):
	text = forms.CharField(widget=forms.Textarea)


class GraderForm(forms.Form):
	text = forms.CharField(widget=forms.Textarea)
