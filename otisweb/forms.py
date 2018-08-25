from registration.forms import RegistrationForm
from django import forms

class ExtendedUserRegistrationForm(RegistrationForm):
	first_name = forms.CharField()
	last_name = forms.CharField()
