import string
from pathlib import Path
from typing import Literal

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http import Http404

StatementFormat = Literal["html", "tex"]


def validate_puid(puid: str) -> None:
    if not puid:
        raise Http404("The PUID cannot be empty.")
    if not all(_ in string.ascii_letters + string.digits for _ in puid):
        raise Http404(f"The PUID {puid} contains illegal characters.")
    elif len(puid) > 32:
        raise Http404(f"The PUID {puid} is too long to be possible.")


def get_disk_statement_from_puid(
    puid: str, fmt: StatementFormat = "html"
) -> str | None:
    """Reads a problem statement for the given PUID off disk.

    The statements live in ``settings.PATH_STATEMENT_ON_DISK`` as
    ``{puid}.html`` (the rendered statement, meant to be displayed as HTML)
    and ``{puid}.tex`` (the raw TeX source of the same statement).
    Returns ``None`` if no such file is available.

    The PUID is used verbatim, so callers are responsible for normalizing
    its case; the files on disk are named after uppercase PUIDs.
    """
    validate_puid(puid)
    if settings.PATH_STATEMENT_ON_DISK is None:
        return None
    base_path = Path(settings.PATH_STATEMENT_ON_DISK).resolve()
    statement_path = (base_path / f"{puid}.{fmt}").resolve()
    # validate_puid already rules out separators and dots, but insist that
    # the statement be a direct child of the statement directory anyway
    if statement_path.parent != base_path:
        raise SuspiciousOperation(f"oh this is really bad ur so screwed ({puid})")
    elif statement_path.exists() and statement_path.is_file():
        return statement_path.read_text()
    else:
        return None
