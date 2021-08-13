from django import forms
from django.contrib.auth.models import User
from django.http.request import HttpRequest


class OTISUserRegistrationForm(forms.Form):
	first_name = forms.CharField(required=False)
	last_name = forms.CharField(required=False)

	def signup(self, request: HttpRequest, user: User):
		if self.is_valid():
			data = self.cleaned_data
			changed = False

			if 'first_name' in data:
				user.first_name = data['first_name']
				changed = True
			if 'last_name' in data:
				user.last_name = data['last_name']
				changed = True

			if changed is True:
				user.save()
