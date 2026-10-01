import io
from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test.utils import override_settings
from django.urls import reverse
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from core.factories import UnitFactory, UserFactory, mock_pdf
from core.utils import CACHE_MAX_AGE_SECONDS
from core.watermark import (
    get_corner_text,
    get_watermark_text,
    verify_corner_stamp,
    watermark_pdf,
)
from roster.factories import StudentFactory


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_pdf_watermark(otis):
    alice = StudentFactory.create(
        user__first_name="Alice",
        user__last_name="Aardvark",
        user__email="alice@example.com",
    )
    unit = UnitFactory.create()
    alice.unlocked_units.add(unit)
    otis.login(alice)

    resp = otis.get_20x("view-problems", unit.pk)
    text = PdfReader(io.BytesIO(resp.content)).pages[0].extract_text()
    assert "Prob" in text  # the original content is still there
    assert "Alice Aardvark" in text
    assert alice.user.username in text
    assert "alice@example.com" in text
    assert f"OTIS PK {alice.user.pk}" in text  # invisible corner stamp
    stamp = verify_corner_stamp(text)
    assert stamp is not None
    assert stamp.pk == alice.user.pk

    # TeX files are served as-is
    assert otis.get_20x("view-tex", unit.pk).content == b"TeX"


@pytest.mark.django_db
def test_watermark_text_transliteration():
    # Names with diacritics are transliterated to ASCII, not dropped as boxes.
    dorde = UserFactory.create(
        first_name="Đorđe", last_name="Petrović", username="dpetrovic"
    )
    text = get_watermark_text(dorde)
    assert "Dorde Petrovic" in text
    assert "dpetrovic" in text
    assert text.isascii()

    # A name unidecode can't turn into anything meaningful is omitted rather
    # than left to render as tofu boxes; username/email still identify them.
    emoji = UserFactory.create(
        first_name="\U0001f389\U0001f389\U0001f389", last_name="", username="emoji_user"
    )
    text = get_watermark_text(emoji)
    assert "emoji_user" in text
    assert emoji.email in text
    assert text.isascii()


@pytest.mark.django_db
def test_watermark_all_pages():
    # A leaker sharing just one page (not necessarily the first) should still
    # be traceable, so every page gets both stamps, not just the first.
    alice = UserFactory.create()
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(612, 792))
    for i in range(3):
        canvas.drawString(72, 720, f"Page {i + 1}")
        canvas.showPage()
    canvas.save()

    out = watermark_pdf(buffer.getvalue(), alice)
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 3
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        assert f"Page {i + 1}" in text
        assert alice.username in text
        stamp = verify_corner_stamp(text)
        assert stamp is not None
        assert stamp.pk == alice.pk


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_protected_file_etag(otis):
    alice = StudentFactory.create()
    unit = UnitFactory.create()
    alice.unlocked_units.add(unit)
    otis.login(alice)

    resp = otis.get_20x("view-problems", unit.pk)
    etag = resp.headers["ETag"]
    assert etag.startswith('W/"')
    assert resp.headers["Cache-Control"] == f"private, max-age={CACHE_MAX_AGE_SECONDS}"
    assert "Cookie" in resp.headers["Vary"]

    with mock.patch(
        "core.utils.watermark_pdf", side_effect=AssertionError("re-watermarked")
    ):
        # browser has cached content and asks if it's fresh:
        again = otis.get("view-problems", unit.pk, headers={"if-none-match": etag})
    assert again.status_code == 304  # not modified
    assert again.content == b""
    assert again.headers["ETag"] == etag
    assert again.headers["Cache-Control"] == f"private, max-age={CACHE_MAX_AGE_SECONDS}"
    assert "Cookie" in again.headers["Vary"]

    stale = otis.get("view-problems", unit.pk, headers={"if-none-match": 'W/"nope"'})
    assert stale.status_code == 200
    assert stale.headers["ETag"] == etag

    tex = otis.get_20x("view-tex", unit.pk)
    tex_again = otis.get(
        "view-tex", unit.pk, headers={"if-none-match": tex.headers["ETag"]}
    )
    assert tex_again.status_code == 304


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_protected_file_etag_is_per_user(otis):
    alice = StudentFactory.create()
    bob = StudentFactory.create()
    unit = UnitFactory.create()
    alice.unlocked_units.add(unit)
    bob.unlocked_units.add(unit)

    otis.login(alice)
    alice_etag = otis.get_20x("view-problems", unit.pk).headers["ETag"]

    otis.login(bob)
    resp = otis.get("view-problems", unit.pk, headers={"if-none-match": alice_etag})
    assert resp.status_code == 200
    assert resp.headers["ETag"] != alice_etag


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
def test_protected_file_etag_invalidation(otis):
    alice = StudentFactory.create()
    unit = UnitFactory.create()
    alice.unlocked_units.add(unit)
    otis.login(alice)
    etag = otis.get_20x("view-problems", unit.pk).headers["ETag"]

    path = f"unit-pdf/{unit.problems_pdf_filename}"
    protected = storages["protected"]
    protected.delete(path)
    protected.save(path, ContentFile(mock_pdf(b"Revised")))
    resp = otis.get("view-problems", unit.pk, headers={"if-none-match": etag})
    assert resp.status_code == 200
    assert resp.headers["ETag"] != etag
    assert "Revised" in PdfReader(io.BytesIO(resp.content)).pages[0].extract_text()


@pytest.mark.django_db
@override_settings(TESTING_NEEDS_MOCK_MEDIA=True)
@pytest.mark.parametrize("error", [NotImplementedError, OSError])
def test_protected_file_without_mtime(otis, error: type[Exception]):
    alice = StudentFactory.create()
    unit = UnitFactory.create()
    alice.unlocked_units.add(unit)
    otis.login(alice)

    def no_mtime(name: str):
        raise error

    with mock.patch.object(
        storages["protected"], "get_modified_time", side_effect=no_mtime
    ):
        resp = otis.get_20x("view-problems", unit.pk)
    assert "ETag" not in resp.headers
    assert "Prob" in PdfReader(io.BytesIO(resp.content)).pages[0].extract_text()


@pytest.mark.django_db
def test_watermark_unparseable_pdf():
    # Serving an unmarked file beats serving a broken one
    alice = UserFactory.create()
    assert watermark_pdf(b"certainly not a PDF", alice) == b"certainly not a PDF"


@pytest.mark.django_db
def test_corner_stamp_tamper_detection():
    alice = UserFactory.create()
    mallory = UserFactory.create()
    text = get_corner_text(alice)
    stamp = verify_corner_stamp(text)
    assert stamp is not None
    assert stamp.pk == alice.pk

    # Mallory can't just edit the pk in a leaked copy to frame Alice, since she
    # doesn't know SECRET_KEY and so can't produce a matching signature.
    forged = text.replace(f"PK {alice.pk} ", f"PK {mallory.pk} ", 1)
    assert verify_corner_stamp(forged) is None

    # Garbage/missing stamps are handled the same way.
    assert verify_corner_stamp("no stamp here") is None


@pytest.mark.django_db
def test_check_stamp(otis):
    admin = UserFactory.create(is_staff=True, is_superuser=True)
    staff_not_admin = UserFactory.create(is_staff=True)
    alice = UserFactory.create(username="alice")
    text = get_corner_text(alice)

    # Access control: only staff+superuser (admin_required) may use this.
    otis.get_30x("check-stamp")
    otis.login(UserFactory.create())
    otis.get_40x("check-stamp")
    otis.login(staff_not_admin)
    otis.get_40x("check-stamp")

    otis.login(admin)
    resp = otis.get_20x("check-stamp")
    assert resp.context["stamp"] is None

    # A genuine stamp resolves to the user and links their userinfo page.
    resp = otis.post_ok("check-stamp", data={"text": f"blah blah {text} blah"})
    assert resp.context["target_user"] == alice
    otis.assert_has(resp, reverse("user-info", args=(alice.pk,)))

    # A forged/garbled stamp resolves to nobody.
    resp = otis.post_ok("check-stamp", data={"text": "not a real stamp"})
    assert resp.context["stamp"] is None
    assert resp.context["target_user"] is None
    otis.assert_message(resp, "No valid stamp found in that text.")
