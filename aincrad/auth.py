"""Token authentication for the aincrad API.

Two tokens are recognized: a full-access one, and a read-only one which may
only run the actions in `READONLY_ACTIONS`. Each is configured as the SHA-256
hexdigest of the token, which is safe as long as the tokens are long random
strings rather than anything memorable.
"""

import logging
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.utils.crypto import constant_time_compare

logger = logging.getLogger(__name__)

READONLY_ACTIONS = frozenset(("init",))


def get_token(request: HttpRequest, fallback: str | None = None) -> str | None:
    """Read the bearer token out of the request, falling back to `fallback`.

    The fallback is the token in the request body, which is how the client
    scripts used to send it and still may.
    """
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return fallback


def token_matches(token: str, target_hash: str) -> bool:
    return constant_time_compare(sha256(token.encode("utf-8")).hexdigest(), target_hash)


def reject_bad_token(token: str | None, action: str) -> JsonResponse | None:
    """Return the response to send if `token` may not do `action`, else None."""
    if token is None:
        raise SuspiciousOperation("No token provided")

    full_hash: str | None = settings.API_TOKEN_HASH_FULL
    readonly_hash: str | None = settings.API_TOKEN_HASH_READONLY
    if full_hash is None and readonly_hash is None:
        return JsonResponse({"error": "Not accepting tokens right now"}, status=503)
    if full_hash is not None and token_matches(token, full_hash):
        return None
    if readonly_hash is not None and token_matches(token, readonly_hash):
        if action in READONLY_ACTIONS:
            return None
        logger.warning(f"Read-only aincrad token was used to try {action}")
        return JsonResponse(
            {"error": f"The read-only token cannot do {action}"}, status=403
        )
    logger.warning(f"Bad token on an aincrad API request to {action}")
    return JsonResponse({"error": "🧋"}, status=418)
