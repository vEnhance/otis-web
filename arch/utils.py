import string
from pathlib import Path
from typing import Literal, Optional

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http import Http404

StatementFormat = Literal["html", "tex"]


def validate_puid(puid: str) -> None:
    if not all(_ in string.ascii_letters + string.digits for _ in puid):
        raise Http404(f"The PUID {puid} contains illegal characters.")
    elif len(puid) > 32:
        raise Http404(f"The PUID {puid} is too long to be possible.")


def get_disk_statement_from_puid(
    puid: str, fmt: StatementFormat = "html"
) -> Optional[str]:
    """Reads a problem statement for the given PUID off disk.

    The statements live in ``settings.PATH_STATEMENT_ON_DISK`` as
    ``{puid}.html`` (the rendered statement, meant to be displayed as HTML)
    and ``{puid}.tex`` (the raw TeX source of the same statement).
    Returns ``None`` if no such file is available.
    """
    validate_puid(puid)
    if settings.PATH_STATEMENT_ON_DISK is None:
        return None
    base_path = Path(settings.PATH_STATEMENT_ON_DISK).resolve()
    statement_path = (base_path / f"{puid}.{fmt}").resolve()
    if statement_path.parent != base_path:
        raise SuspiciousOperation(f"oh this is really bad ur so screwed ({puid})")
    elif statement_path.exists() and statement_path.is_file():
        return statement_path.read_text()
    else:
        return None
