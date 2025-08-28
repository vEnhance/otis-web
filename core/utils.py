import logging
from hashlib import sha256

from django.conf import settings
from django.core.files.storage import default_storage
from django.http.response import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseServerError,
)

logger = logging.getLogger(__name__)


def storage_hash(value: str) -> str:
    s = f"{settings.STORAGE_HASH_KEY}|{value}"
    h = sha256(s.encode("ascii")).hexdigest()
    return f"TESTING_{h}" if settings.TESTING else h


def get_from_google_storage(filename: str):
    ext = filename[-4:]
    if ext not in [".tex", ".pdf"]:
        return HttpResponseBadRequest("Bad filename extension")

    path = f"protected/{storage_hash(filename)}{ext}"
    try:
        file = default_storage.open(path)
    except FileNotFoundError:
        errmsg = f"Unable to find {filename} at {path}."
        logger.critical(errmsg)
        return HttpResponseServerError(errmsg)

    response = HttpResponse(content=file)
    if ext == ".pdf":
        response["Content-Type"] = "application/pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
    else:
        response["Content-Type"] = "text/plain"
        response["Content-Disposition"] = "inline"

    return response
