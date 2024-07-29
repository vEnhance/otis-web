from django import forms


class AttemptForm(forms.Form):
    guess = forms.CharField(max_length=128, label="Submit an answer")
