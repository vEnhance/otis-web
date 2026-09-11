import zoneinfo
from collections.abc import Callable

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils import timezone

from .models import UserProfile
from .utils import find_profile


class LastSeenMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    # following the idea of https://stackoverflow.com/a/57344768/4826845
    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        if not isinstance(request.user, User) or not request.session.session_key:
            return response
        key = f"last-seen-{request.session.session_key}"
        recently_seen = cache.get(key)
        if not recently_seen:
            cache.set(key, 1, 60 * 15)  # we won't update last_seen for 15 minutes
            UserProfile.objects.update_or_create(
                user=request.user, defaults={"last_seen": timezone.now()}
            )
        return response


class TimezoneMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if isinstance(request.user, User):
            up = find_profile(request.user)
            if up is not None and up.timezone:
                try:
                    timezone.activate(zoneinfo.ZoneInfo(up.timezone))
                except zoneinfo.ZoneInfoNotFoundError:
                    pass  # Fall back to default timezone
        response = self.get_response(request)
        timezone.deactivate()
        return response
