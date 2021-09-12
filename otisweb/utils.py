from django.contrib.auth.models import User
from django.http import HttpRequest


class AuthHttpRequest(HttpRequest):
	user: User
