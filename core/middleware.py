from typing import Callable

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils import timezone

from .models import UserProfile


class LastSeenMiddleware:
	def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
		self.get_response = get_response

	def __call__(self, request: HttpRequest):
		response = self.get_response(request)
		if not request.user.is_authenticated:
			return response
		up, _ = UserProfile.objects.get_or_create(user=request.user)
		up.last_seen = timezone.now()
		up.save()
		return response
