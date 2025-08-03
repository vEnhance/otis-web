import datetime
import logging
from typing import Optional

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils import timezone

logger = logging.getLogger(__name__)


class AuthHttpRequest(HttpRequest):
    user: User


def get_days_since(t: Optional[datetime.datetime]) -> Optional[float]:
    if t is None:
        return None
    return (timezone.now() - t).total_seconds() / (3600 * 24)
