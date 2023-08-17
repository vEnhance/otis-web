from typing import Callable

from django.core.cache import cache
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils import timezone

from .models import UserProfile


class LastSeenMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    # following the idea of https://stackoverflow.com/a/57344768/4826845
    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        if not request.user.is_authenticated or not request.session.session_key:
            return response
        up, _ = UserProfile.objects.get_or_create(user=request.user)
        key = f"last-seen-{request.session.session_key}"
        recently_seen = cache.get(key)
        if not recently_seen:
            cache.set(key, 1, 60 * 15)  # we won't update last_seen for 15 minutes
            up.last_seen = timezone.now()
            up.save(update_fields=("last_seen",))
        return response
