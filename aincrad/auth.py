"""Token authentication for the aincrad API.

The token is configured as the SHA-256 hexdigest, which is safe as long as
the token is a long random string rather than anything memorable.
"""

import logging
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.utils.crypto import constant_time_compare

logger = logging.getLogger(__name__)


def get_token(request: HttpRequest) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return None


def token_matches(token: str, target_hash: str) -> bool:
    return constant_time_compare(sha256(token.encode("utf-8")).hexdigest(), target_hash)


def reject_bad_token(token: str | None, action: str) -> JsonResponse | None:
    """Return the response to send if `token` is not accepted, else None."""
    if token is None:
        raise SuspiciousOperation("No token provided")

    target_hash: str | None = settings.API_TARGET_HASH
    if target_hash is None:
        return JsonResponse({"error": "Not accepting tokens right now"}, status=503)
    if token_matches(token, target_hash):
        return None
    logger.warning(f"Bad token on an aincrad API request to {action}")
    return JsonResponse({"error": "🧋"}, status=418)
