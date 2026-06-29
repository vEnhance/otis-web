import logging

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.storage import storages
from django.http import HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from storages.backends.s3 import S3Storage

from core.models import UserProfile

logger = logging.getLogger(__name__)

PROTECTED_FILE_URL_EXPIRE_SECONDS = 30


def get_protected_file(folder: str, filename: str, request: HttpRequest):
    if not isinstance(request.user, User):
        raise PermissionDenied("Only logged in users may query core storage.")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    inline_pdf = profile.inline_pdf
    inline_tex = profile.inline_tex
    ext = filename[-4:]
    if ext not in [".tex", ".pdf"]:
        return HttpResponseBadRequest("Bad filename extension")

    if ext == ".pdf":
        content_type = "application/pdf"
        disposition = (
            f'{"inline" if inline_pdf else "attachment"}; filename="{filename}"'
        )
    else:
        content_type = "text/plain"
        disposition = (
            f'{"inline" if inline_tex else "attachment"}; filename="{filename}"'
        )

    path = f"{folder}/{filename}"
    storage = storages["protected"]

    # On production the protected storage is S3Storage (R2-backed), which can
    # mint presigned URLs locally without touching the network. Redirect the
    # client directly to R2 so file bytes never pass through our server.
    if isinstance(storage, S3Storage):
        url = storage.url(
            path,
            parameters={
                "ResponseContentType": content_type,
                "ResponseContentDisposition": disposition,
            },
            expire=PROTECTED_FILE_URL_EXPIRE_SECONDS,
        )
        return HttpResponseRedirect(url)

    # Fallback: stream the file through Django (used in dev/test with InMemoryStorage).
    try:
        file = storage.open(path)
    except FileNotFoundError:
        errmsg = f"Unable to find {filename} at {path}."
        logger.critical(errmsg)
        return HttpResponseServerError("File not found")

    response = HttpResponse(content=file)
    response["Content-Type"] = content_type
    response["Content-Disposition"] = disposition
    return response
