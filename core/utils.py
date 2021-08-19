import logging
from hashlib import sha256

from django.conf import settings
from django.core.files.storage import default_storage
from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseServerError  # NOQA

logger = logging.getLogger(__name__)


def h(value: str) -> str:
	s = settings.STORAGE_HASH_KEY + '|' + value
	return sha256(s.encode('ascii')).hexdigest()


def get_from_google_storage(filename: str):
	if settings.TESTING:
		return HttpResponse('Retrieved file')
	ext = filename[-4:]
	if not (ext == '.tex' or ext == '.pdf'):
		return HttpResponseBadRequest('Bad filename extension')
	try:
		file = default_storage.open('pdfs/' + h(filename) + ext)
	except FileNotFoundError:
		errmsg = f"Unable to find {filename}."
		logger.critical(errmsg)
		return HttpResponseServerError(errmsg)
	response = HttpResponse(content=file)
	response['Content-Type'] = f'application/{ext}'
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response
