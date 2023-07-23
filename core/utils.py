import logging
from hashlib import sha256

from django.conf import settings
from django.core.files.storage import default_storage
from django.http.response import (  # NOQA
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseServerError,
)

logger = logging.getLogger(__name__)


def storage_hash(value: str) -> str:
    s = settings.STORAGE_HASH_KEY + "|" + value
    h = sha256(s.encode("ascii")).hexdigest()
    if settings.TESTING:
        return f"TESTING_{h}"
    else:
        return h


def get_from_google_storage(filename: str):
    ext = filename[-4:]
    if not (ext == ".tex" or ext == ".pdf"):
        return HttpResponseBadRequest("Bad filename extension")

    path = "protected/" + storage_hash(filename) + ext
    try:
        file = default_storage.open(path)
    except FileNotFoundError:
        errmsg = f"Unable to find {path}."
        logger.critical(errmsg)
        return HttpResponseServerError(errmsg)

    response = HttpResponse(content=file)
    response["Content-Type"] = f"application/{ext}"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
