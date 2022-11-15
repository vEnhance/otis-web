from django import forms


class DiamondsForm(forms.Form):
	code = forms.CharField(label="", max_length=64, required=True)
