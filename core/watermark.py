"""Stamps a per-user, tamper-evident watermark onto protected PDF downloads.

See `verify_corner_stamp` for how to check a stamp's authenticity.
"""

import datetime
import hmac
import io
import logging
import re
from typing import NamedTuple

from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.crypto import salted_hmac
from pypdf import PageObject, PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen.canvas import Canvas
from unidecode import unidecode

logger = logging.getLogger(__name__)

FONT_NAME = "Helvetica-Oblique"
FONT_SIZE = 7
MIN_FONT_SIZE = 4
RIGHT_MARGIN = 12  # points from the right edge of the page to the text baseline
END_MARGIN = 18  # points of clearance at the top and bottom of the page
VISIBLE_COLOR = Color(0.45, 0.45, 0.45, alpha=0.85)

CORNER_MARGIN = 8  # points from the bottom-right corner of the page
CORNER_FONT_SIZE = 6
INVISIBLE_COLOR = Color(1, 1, 1, alpha=0.05)

WATERMARK_SALT = "core.watermark"
SIG_LENGTH = 32  # hex chars (128 bits) of the HMAC-SHA256 digest; plenty
CORNER_STAMP_RE = re.compile(rf"OTIS PK (\d+) TS (\d+) SIG ([0-9a-f]{{{SIG_LENGTH}}})")


def get_watermark_text(user: User) -> str:
    """Return the line of text identifying `user` as the downloader.

    The stamp font only covers ASCII, so names are transliterated; a name
    unidecode can't render as anything meaningful is dropped rather than
    shown as boxes, falling back to username/email.
    """
    full_name = unidecode(user.get_full_name()).strip()
    username = unidecode(user.username).strip()
    parts = [full_name, username, user.email]
    who = " / ".join(part for part in parts if part)
    when = timezone.now().strftime("%Y-%m-%d %H:%M %Z")
    return f"Downloaded from OTIS by {who} on {when}. Not for redistribution."


def _sign(payload: str) -> str:
    """Return a keyed digest of `payload`."""
    return salted_hmac(WATERMARK_SALT, payload, algorithm="sha256").hexdigest()[
        :SIG_LENGTH
    ]


def get_corner_text(user: User) -> str:
    """Return the invisible corner stamp: a signed pk and timestamp."""
    epoch = int(timezone.now().timestamp())
    sig = _sign(f"{user.pk}:{epoch}")
    return f"OTIS PK {user.pk} TS {epoch} SIG {sig}"


class CornerStamp(NamedTuple):
    pk: int
    when: datetime.datetime


def verify_corner_stamp(text: str) -> CornerStamp | None:
    """Return the pk and timestamp from a valid stamp in `text`, else None."""
    match = CORNER_STAMP_RE.search(text)
    if match is None:
        return None
    pk, epoch, sig = match.groups()
    if not hmac.compare_digest(_sign(f"{pk}:{epoch}"), sig):
        return None
    when = datetime.datetime.fromtimestamp(int(epoch), tz=datetime.UTC)
    return CornerStamp(pk=int(pk), when=when)


def _build_margin_overlay(text: str, page: PageObject) -> PageObject:
    """Return a single-page PDF holding the rotated right-margin stamp."""
    box = page.mediabox
    bottom = float(box.bottom)
    right, top = float(box.right), float(box.top)

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(right, top))
    canvas.setFillColor(VISIBLE_COLOR)

    # Shrink to fit between the top and bottom margins.
    font_size = FONT_SIZE
    max_length = (top - bottom) - 2 * END_MARGIN
    while (
        font_size > MIN_FONT_SIZE
        and canvas.stringWidth(text, FONT_NAME, font_size) > max_length
    ):
        font_size -= 0.5

    canvas.setFont(FONT_NAME, font_size)
    canvas.saveState()
    canvas.translate(right - RIGHT_MARGIN, bottom)
    canvas.rotate(90)
    canvas.drawCentredString((top - bottom) / 2, 0, text)
    canvas.restoreState()
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def _build_corner_overlay(text: str, page: PageObject) -> PageObject:
    """Return a single-page PDF holding the invisible bottom-right stamp."""
    box = page.mediabox
    bottom, right = float(box.bottom), float(box.right)
    top = float(box.top)

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(right, top))
    canvas.setFillColor(INVISIBLE_COLOR)
    canvas.setFont(FONT_NAME, CORNER_FONT_SIZE)
    canvas.drawRightString(right - CORNER_MARGIN, bottom + CORNER_MARGIN, text)
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def watermark_pdf(content: bytes, user: User) -> bytes:
    """Return `content` with `user` stamped on every page.

    Watermarking is best-effort: if the bytes cannot be parsed as a PDF (or the
    stamping otherwise fails) the original content is returned unchanged, since
    serving an unmarked file beats serving a broken one.
    """
    try:
        writer = PdfWriter(clone_from=io.BytesIO(content))
        if not writer.pages:
            return content

        margin_text = get_watermark_text(user)
        corner_text = get_corner_text(user)
        # Reuse overlays across pages that share a mediabox.
        overlays: dict[
            tuple[float, float, float, float], tuple[PageObject, PageObject]
        ] = {}
        for page in writer.pages:
            box = page.mediabox
            key = (float(box.left), float(box.bottom), float(box.right), float(box.top))
            if key not in overlays:
                overlays[key] = (
                    _build_margin_overlay(margin_text, page),
                    _build_corner_overlay(corner_text, page),
                )
            margin_overlay, corner_overlay = overlays[key]
            page.merge_page(margin_overlay)
            page.merge_page(corner_overlay)

        # merge_page leaves page content streams uncompressed and the
        # now-unreferenced original stream objects still in the file, which
        # roughly quadruples output size on a content-heavy PDF. Recompress
        # and prune before writing.
        for page in writer.pages:
            page.compress_content_streams()
        writer.compress_identical_objects(
            remove_duplicates=True, remove_unreferenced=True
        )

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except Exception:
        logger.exception("Could not watermark a PDF for %s, serving as-is", user)
        return content
