import logging

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.storage import Storage, storages
from django.http import Http404, HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseServerError,
)
from django.utils.cache import get_conditional_response
from django.utils.crypto import salted_hmac

from core.models import UserProfile
from core.watermark import watermark_pdf

logger = logging.getLogger(__name__)

ETAG_SALT = "core.utils.protected_file"
ETAG_LENGTH = 32

CACHE_MAX_AGE_SECONDS = 15 * 60


def get_protected_etag(storage: Storage, path: str, user: User) -> str | None:
    try:
        mtime = storage.get_modified_time(path)
    except Exception:
        logger.exception("Could not stat %s, serving it unconditionally", path)
        return None
    payload = f"{path}:{mtime.timestamp()}:{user.pk}"
    digest = salted_hmac(ETAG_SALT, payload, algorithm="sha256").hexdigest()
    return f'W/"{digest[:ETAG_LENGTH]}"'


def add_cache_headers(response: HttpResponse, etag: str | None) -> HttpResponse:
    if etag is not None:
        response["ETag"] = etag
    response["Cache-Control"] = f"private, max-age={CACHE_MAX_AGE_SECONDS}"
    return response


def get_protected_file(
    folder: str, filename: str, request: HttpRequest, missing_is_404: bool = False
):
    if not isinstance(request.user, User):
        raise PermissionDenied("Only logged in users may query core storage.")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    inline_pdf = profile.inline_pdf
    inline_tex = profile.inline_tex
    ext = filename[-4:]
    if ext not in [".tex", ".pdf"]:
        return HttpResponseBadRequest("Bad filename extension")

    path = f"{folder}/{filename}"
    storage = storages["protected"]
    try:
        file = storage.open(path)
    except FileNotFoundError:
        if missing_is_404:
            raise Http404(f"No file named {filename} is available.")
        errmsg = f"Unable to find {filename} at {path}."
        logger.critical(errmsg)
        return HttpResponseServerError("File not found")

    with file:
        etag = get_protected_etag(storage, path, request.user)
        conditional_response = get_conditional_response(request, etag=etag)
        if conditional_response is not None:
            return add_cache_headers(conditional_response, etag)
        content = file.read()

    if ext == ".pdf":
        response = HttpResponse(content=watermark_pdf(content, request.user))
        response["Content-Type"] = "application/pdf"
        response["Content-Disposition"] = (
            f'{"inline" if inline_pdf else "attachment"}; filename="{filename}"'
        )
    else:
        response = HttpResponse(content=content)
        response["Content-Type"] = "text/plain; charset=utf-8"
        response["Content-Disposition"] = (
            f'{"inline" if inline_tex else "attachment"}; filename="{filename}"'
        )

    return add_cache_headers(response, etag)
