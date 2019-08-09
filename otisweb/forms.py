from django_registration.forms import RegistrationForm
from django import forms

class OTISUserRegistrationForm(RegistrationForm):
	first_name = forms.CharField()
	last_name = forms.CharField()
