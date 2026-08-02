"""Stamps a per-user watermark onto protected PDF files.

The watermark is a single line of small print placed in the bottom margin of the
first page, naming the user who requested the download.  It is drawn into the
page content stream (rather than added as an annotation) so that it cannot be
stripped by simply toggling annotations off in a PDF viewer.
"""

import io
import logging

from django.contrib.auth.models import User
from django.utils import timezone
from pypdf import PageObject, PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen.canvas import Canvas

logger = logging.getLogger(__name__)

FONT_NAME = "Helvetica-Oblique"
FONT_SIZE = 7
MIN_FONT_SIZE = 4
BOTTOM_MARGIN = 18  # points above the bottom edge of the page
SIDE_MARGIN = 18  # points of clearance on each side
COLOR = Color(0.45, 0.45, 0.45, alpha=0.85)


def get_watermark_text(user: User) -> str:
    """Return the line of text identifying `user` as the downloader."""
    parts = [user.get_full_name(), user.username, user.email]
    who = " / ".join(part for part in parts if part)
    when = timezone.now().strftime("%Y-%m-%d %H:%M %Z")
    return f"Downloaded from OTIS by {who} on {when}. Not for redistribution."


def _build_overlay(text: str, page: PageObject) -> PageObject:
    """Return a single-page PDF holding just the watermark for `page`.

    The overlay is drawn in the same user space as `page`, so a media box whose
    origin is not (0, 0) still gets its watermark in the bottom margin.
    """
    box = page.mediabox
    left, bottom = float(box.left), float(box.bottom)
    right, top = float(box.right), float(box.top)

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(right, top))
    canvas.setFillColor(COLOR)

    # Shrink the text until it fits between the side margins, so that a long
    # name or email address does not run off the edge of the page.
    font_size = FONT_SIZE
    max_width = (right - left) - 2 * SIDE_MARGIN
    while (
        font_size > MIN_FONT_SIZE
        and canvas.stringWidth(text, FONT_NAME, font_size) > max_width
    ):
        font_size -= 0.5

    canvas.setFont(FONT_NAME, font_size)
    canvas.drawCentredString((left + right) / 2, bottom + BOTTOM_MARGIN, text)
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def watermark_pdf(content: bytes, user: User) -> bytes:
    """Return `content` with `user` stamped on the first page.

    Watermarking is best-effort: if the bytes cannot be parsed as a PDF (or the
    stamping otherwise fails) the original content is returned unchanged, since
    serving an unmarked file beats serving a broken one.
    """
    try:
        writer = PdfWriter(clone_from=io.BytesIO(content))
        if not writer.pages:
            return content
        first_page = writer.pages[0]
        first_page.merge_page(_build_overlay(get_watermark_text(user), first_page))
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except Exception:
        logger.exception("Could not watermark a PDF for %s, serving as-is", user)
        return content
