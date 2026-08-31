from hashlib import sha256

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

from arch.factories import HintFactory, ProblemFactory
from arch.models import Hint, Problem
from core.factories import SemesterFactory, UnitFactory, UserFactory, UserProfileFactory
from dashboard.factories import PSetFactory
from dashboard.models import Announcement
from hanabi.factories import HanabiContestFactory, HanabiPlayerFactory
from hanabi.models import HanabiParticipation, HanabiReplay
from opal.factories import OpalHuntFactory, OpalPuzzleFactory
from opal.models import OpalPuzzle
from payments.factories import PaymentLogFactory
from roster.factories import (
    InvoiceFactory,
    RegistrationContainerFactory,
    StudentFactory,
    StudentRegistrationFactory,
    UnitPetitionFactory,
)
from roster.models import ApplyUUID, Invoice, Student, UnitPetition

EXAMPLE_PASSWORD = "take just the first 24"
TARGET_HASH = sha256(EXAMPLE_PASSWORD.encode("ascii")).hexdigest()


def opal_pdf(body: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile("tetrogram.pdf", b"%PDF-1.4 " + body)


@pytest.fixture
def aincrad_setup(db):
    active_semester = SemesterFactory.create(name="New")
    old_semester = SemesterFactory.create(name="Old", active=False)

    alice = StudentFactory.create(
        user__first_name="Alice",
        user__last_name="Aardvárk",
        user__username="alice",
        user__email="alice@example.org",
        semester=active_semester,
    )
    bob = StudentFactory.create(
        user__first_name="Bôb B.",
        user__last_name="Bèta",
        user__username="bob",
        user__email="bob@example.org",
        semester=active_semester,
    )
    carol = StudentFactory.create(
        user__first_name="Carol",
        user__last_name="Cutie",
        user__username="carol",
        user__email="carol@example.org",
        semester=active_semester,
    )
    david = StudentFactory.create(
        user__first_name="David",
        user__last_name="Darling",
        user__username="david",
        user__email="david@example.org",
        semester=active_semester,
    )
    eve = StudentFactory.create(
        user__first_name="Eve",
        user__last_name="Edgeworth",
        user__username="eve",
        user__email="edge@wor.th",
        semester=active_semester,
    )
    UserProfileFactory.create(user=alice.user, email_on_announcement=True)
    UserProfileFactory.create(user=bob.user, email_on_announcement=True)
    UserProfileFactory.create(user=carol.user, email_on_announcement=True)
    UserProfileFactory.create(user=david.user, email_on_announcement=False)
    UserProfileFactory.create(user=eve.user, email_on_announcement=True)
    old_alice = StudentFactory.create(user=alice.user, semester=old_semester)

    submitted_unit, requested_unit = UnitFactory.create_batch(2)
    PSetFactory.create(
        student=alice,
        unit=submitted_unit,
        next_unit_to_unlock=requested_unit,
        clubs=120,
        hours=37,
        status="P",
        feedback="Meow",
        special_notes="Purr",
    )
    PSetFactory.create_batch(2, student=bob, status="P")
    PSetFactory.create_batch(3, student=carol, status="P")
    PSetFactory.create_batch(7, student=alice, status="A")
    PSetFactory.create_batch(2, student=alice, status="R")
    PSetFactory.create_batch(4, student=alice, status="P")
    PSetFactory.create_batch(3, student=david, status="A")
    PSetFactory.create_batch(4, student=old_alice, status="A")
    PSetFactory.create_batch(2, student=old_alice, status="P")

    UnitPetitionFactory.create_batch(
        5, student=alice, action_type="PET_ACT_UNLOCK", status="PET_ACC"
    )
    UnitPetitionFactory.create_batch(
        2, student=alice, action_type="PET_ACT_DROP", status="PET_ACC"
    )
    UnitPetitionFactory.create_batch(
        3, student=alice, action_type="PET_ACT_UNLOCK", status="PET_NEW"
    )

    alice.curriculum.add(submitted_unit)
    alice.curriculum.add(requested_unit)
    alice.unlocked_units.add(submitted_unit)

    InvoiceFactory.create(student=alice, total_paid=250)
    InvoiceFactory.create(student=bob)
    invC = InvoiceFactory.create(student=carol, total_paid=210)
    invD = InvoiceFactory.create(student=david, total_paid=480)
    invE = InvoiceFactory.create(student=eve, total_paid=1)
    PaymentLogFactory.create(invoice=invC, amount=50)
    PaymentLogFactory.create(invoice=invC, amount=70)
    PaymentLogFactory.create(invoice=invC, amount=90)
    PaymentLogFactory.create(invoice=invC, amount=9001, refunded=True)
    PaymentLogFactory.create(invoice=invD, amount=360)
    PaymentLogFactory.create(invoice=invD, amount=120)
    PaymentLogFactory.create(invoice=invE, amount=1)
    PaymentLogFactory.create(invoice=invC, amount=9001, refunded=True)

    regcontainer_active = RegistrationContainerFactory.create(semester=active_semester)
    regcontainer_old = RegistrationContainerFactory.create(semester=old_semester)

    for student in (alice, bob, carol, david, eve, old_alice):
        StudentRegistrationFactory.create(
            user=student.user,
            container=(
                regcontainer_active
                if student.semester.active is True
                else regcontainer_old
            ),
        )


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_init(otis, aincrad_setup):
    resp = otis.post_20x(
        "api",
        json={
            "action": "init",
            "token": EXAMPLE_PASSWORD,
        },
    )
    out = resp.json()
    assert out["_name"] == "Root"
    assert len(out["_children"][0]["_children"]) == 10
    assert "timestamp" in out
    assert len(out.keys()) == 4

    pset_data = out["_children"][0]
    assert pset_data["_name"] == "Problem sets"

    # psets from past semesters should not show up at all
    old_alice_pk = Student.objects.get(semester__active=False).pk
    assert all(pset["student__pk"] != old_alice_pk for pset in pset_data["_children"])

    for pset in pset_data["_children"]:
        if pset["feedback"] == "Meow":
            assert pset["status"] == "P"
            assert pset["clubs"] == 120
            assert pset["hours"] == 37
            assert pset["feedback"] == "Meow"
            assert pset["special_notes"] == "Purr"
            assert pset["student__user__first_name"] == "Alice"
            assert pset["num_accepted_all"] == 11
            assert pset["num_accepted_current"] == 7
            break
    else:
        pytest.fail("Could not find Alice's pset0 in aincrad test")
    for pset in pset_data["_children"]:
        if pset["student__user__first_name"] == "Bôb B.":
            assert pset["status"] == "P"
            assert pset["num_accepted_all"] == 0
            assert pset["num_accepted_current"] == 0
            break
    else:
        pytest.fail("Could not find a pset from Bôb B. in aincrad test")

    petitions = out["_children"][1]["petitions"]
    assert len(petitions) == 3
    assert petitions[0]["unlock_petition_count"] == 8


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_invoice(otis, aincrad_setup):
    out = otis.post_20x(
        "api",
        json={
            "action": "invoice",
            "token": EXAMPLE_PASSWORD,
            "field": "adjustment",
            "entries": {
                "alice.aardvark": -240,
                "edge@wor.th": -474,
                "l.lawliet": 1337,
            },
        },
    ).json()
    assert out["updated_count"] == 2
    assert set(out["updated_names_list"]) == {
        "Alice Aardvárk <alice@example.org>",
        "Eve Edgeworth <edge@wor.th>",
    }
    assert len(out["entries_remaining"]) == 1
    assert "l.lawliet" in out["entries_remaining"]

    out = otis.post_20x(
        "api",
        json={
            "action": "invoice",
            "token": EXAMPLE_PASSWORD,
            "field": "extras",
            "entries": {
                Student.objects.get(
                    user__first_name="Alice", semester__active=True
                ).pk: 10,
                "david.darling": 10,
                "mihael.keehl": -9001,
            },
        },
    ).json()
    assert out["updated_count"] == 2
    assert set(out["updated_names_list"]) == {
        "Alice Aardvárk <alice@example.org>",
        "David Darling <david@example.org>",
    }
    assert len(out["entries_remaining"]) == 1
    assert "mihael.keehl" in out["entries_remaining"]

    out = otis.post_20x(
        "api",
        json={
            "action": "invoice",
            "token": EXAMPLE_PASSWORD,
            "field": "total_paid",
            "entries": {
                "alice.aardvark": 250,
                "bob.beta": 480,
                Student.objects.get(
                    user__first_name="Carol", user__last_name="Cutie"
                ).pk: 110,
                "eve.edgeworth": 5,
                "nate.river": 1152,
            },
        },
    ).json()
    assert out["updated_count"] == 3
    assert set(out["updated_names_list"]) == {
        "Bôb B. Bèta <bob@example.org>",
        "Carol Cutie <carol@example.org>",
        "Eve Edgeworth <edge@wor.th>",
    }
    assert len(out["entries_remaining"]) == 1
    assert "nate.river" in out["entries_remaining"]

    # check the invoices are correct
    invoice_alice = Invoice.objects.get(student__user__first_name="Alice")
    invoice_bob = Invoice.objects.get(student__user__first_name="Bôb B.")
    invoice_carol = Invoice.objects.get(student__user__first_name="Carol")
    invoice_david = Invoice.objects.get(student__user__first_name="David")
    invoice_eve = Invoice.objects.get(student__user__first_name="Eve")

    assert invoice_alice.adjustment == pytest.approx(-240)
    assert invoice_alice.extras == pytest.approx(10)
    assert invoice_alice.total_paid == pytest.approx(250)

    assert invoice_bob.adjustment == pytest.approx(0)
    assert invoice_bob.extras == pytest.approx(0)
    assert invoice_bob.total_paid == pytest.approx(480)

    assert invoice_carol.adjustment == pytest.approx(0)
    assert invoice_carol.extras == pytest.approx(0)
    assert invoice_carol.total_paid == pytest.approx(320)

    assert invoice_david.adjustment == pytest.approx(0)
    assert invoice_david.extras == pytest.approx(10)
    assert invoice_david.total_paid == pytest.approx(480)

    assert invoice_eve.adjustment == pytest.approx(-474)
    assert invoice_eve.extras == pytest.approx(0)
    assert invoice_eve.total_paid == pytest.approx(6)


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_accept_petitions(otis, aincrad_setup):
    resp = otis.post_20x(
        "api",
        json={
            "action": "accept_petitions",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert resp.json()["result"] == "success"
    assert resp.json()["count"] == 3
    assert not UnitPetition.objects.filter(status="PET_NEW").exists()


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_email(otis, aincrad_setup):
    resp = otis.post_20x(
        "api",
        json={
            "action": "email_list",
            "token": EXAMPLE_PASSWORD,
        },
    )
    students = resp.json()["students"]
    assert len(students) == 4
    for s in students:
        if s["user__username"] == "eve":
            assert s["user__email"] == "edge@wor.th"
        else:
            for x in ("alice", "bob", "carol"):
                if s["user__username"] == x:
                    assert s["user__email"] == f"{x}@example.org"
                    break
            else:
                raise ValueError


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_failed_auth(otis):
    resp = otis.post_40x(
        "api",
        json={
            "action": "init",
            "token": "this wrong password is not a puzzle",
        },
    )
    assert resp.status_code == 418


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_get_add_hints(otis):
    HintFactory.create_batch(10)

    resp = otis.post_20x(
        "api",
        json={
            "action": "get_hints",
            "puid": "18SLA7",
            "token": EXAMPLE_PASSWORD,
        },
    )
    out = resp.json()
    assert len(out["hints"]) == 0

    A7_Hints = Hint.objects.filter(problem__puid="18SLA7")

    resp = otis.post_20x(
        "api",
        json={
            "action": "add_hints",
            "puid": "18SLA7",
            "content": "get",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert "pk" in resp.json()
    assert resp.json()["number"] == 0
    resp = otis.post_20x(
        "api",
        json={
            "action": "add_hints",
            "puid": "18SLA7",
            "content": "good",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert "pk" in resp.json()
    assert resp.json()["number"] == 10

    resp = otis.post_20x(
        "api",
        json={
            "action": "get_hints",
            "puid": "18SLA7",
            "token": EXAMPLE_PASSWORD,
        },
    )
    out = resp.json()
    assert len(out["hints"]) == 2
    assert A7_Hints.filter(number=0, content="get").exists()
    assert A7_Hints.filter(number=10, content="good").exists()

    resp = otis.post_20x(
        "api",
        json={
            "action": "add_many_hints",
            "allow_delete_hints": False,
            "puid": "18SLA7",
            "new_hints": [
                {"number": 80, "content": "80%", "keywords": "eighty"},
                {"number": 90, "content": "90%", "keywords": "ninety"},
                {"number": 70, "content": "70%", "keywords": "seventy"},
            ],
            "old_hints": list(
                A7_Hints.values(
                    "keywords",
                    "pk",
                    "number",
                    "content",
                )
            ),
            "token": EXAMPLE_PASSWORD,
        },
    )
    out = resp.json()
    assert len(out["pks"]) == 3
    assert out["num_deletes"] == 0
    assert A7_Hints.filter(number=80, content="80%", keywords="eighty").exists()
    assert A7_Hints.filter(number=70, content="70%", keywords="seventy").exists()
    assert A7_Hints.filter(number=90, content="90%", keywords="ninety").exists()

    # try and fail to delete hints
    otis.post_40x(
        "api",
        json={
            "action": "add_many_hints",
            "allow_delete_hints": False,
            "puid": "18SLA7",
            "new_hints": [],
            "old_hints": [],
            "token": EXAMPLE_PASSWORD,
        },
    )

    # OK, so at this point we have, what, 5 hints?
    # alright let's edit some more
    resp = otis.post_20x(
        "api",
        json={
            "action": "add_many_hints",
            "allow_delete_hints": True,
            "puid": "18SLA7",
            "new_hints": [{"number": 100, "content": "100%", "keywords": "hundred"}],
            "old_hints": [
                {
                    "pk": A7_Hints.get(number=80).pk,
                    "number": 85,
                    "content": "Updated 85%",
                    "keywords": "updated",
                },
                {
                    "pk": A7_Hints.get(number=90).pk,
                    "number": 95,
                    "content": "Updated 95%",
                    "keywords": "updated",
                },
            ],
            "token": EXAMPLE_PASSWORD,
        },
    )
    out = resp.json()
    assert len(out["pks"]) == 1
    assert out["num_deletes"] == 3  # 0%, 10%, 70%
    assert set(A7_Hints.values_list("number", flat=True)) == {85, 95, 100}
    assert A7_Hints.filter(keywords="updated").count() == 2
    assert A7_Hints.filter(keywords__startswith="Updated").count() == 2


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_arch_url_update(otis):
    ProblemFactory.create(
        puid="19USEMO1",
        hyperlink="https://aops.com/community/p15412066",
    )
    ProblemFactory.create(
        puid="19USEMO2",
        hyperlink="https://aops.com/community/p15412166",
    )
    ProblemFactory.create(
        puid="19USEMO3",
        hyperlink="https://wrong.url.to.fix/",
    )
    ProblemFactory.create(
        puid="19USEMO4",
        hyperlink="https://aops.com/community/p15425708",
    )
    ProblemFactory.create(
        puid="19USEMO5",
        hyperlink="https://aops.com/community/p15425728",
    )
    ProblemFactory.create(
        puid="19USEMO6",
    )

    resp = otis.post_20x(
        "api",
        json={
            "action": "arch_url_update",
            "urls": {
                "19USEMO3": "https://aops.com/community/p15412083",
                "19USEMO5": "https://aops.com/community/p15425728",
                "19USEMO6": "https://aops.com/community/p15425714",
                "18SLA7": "https://aops.com/community/p12752777",
            },
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert resp.json()["updated_count"] == 2
    assert resp.json()["created_count"] == 1
    assert (
        Problem.objects.get(puid="19USEMO3").hyperlink
        == "https://aops.com/community/p15412083"
    )
    assert (
        Problem.objects.get(puid="19USEMO6").hyperlink
        == "https://aops.com/community/p15425714"
    )
    assert (
        Problem.objects.get(puid="18SLA7").hyperlink
        == "https://aops.com/community/p12752777"
    )


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_hanabi_contest(otis):
    HANABI_PLAYERS = (
        "alsodqed",
        "anotherplayer1",
        "dqed",
        "dupe1",
        "dupe2",
        "dupe3",
        "player1",
        "player2",
        "player3",
        "runnerup1",
        "runnerup2",
        "winner1",
        "winner2",
        "winner3",
    )
    for u in HANABI_PLAYERS:
        HanabiPlayerFactory.create(hanab_username=u)
    contest = HanabiContestFactory.create(
        variant_id=1,
        variant_name="4 Suits",
        num_suits=4,
    )

    resp = otis.post_20x(
        "api",
        json={
            "action": "hanabi_results",
            "pk": contest.pk,
            "replays": [
                {
                    "players": ["winner1", "winner2", "winner3"],
                    "turn_count": 42,
                    "game_score": 20,
                    "replay_id": 812,
                },
                {
                    "players": ["runnerup1", "runnerup2", "dqed"],
                    "turn_count": 44,
                    "game_score": 20,
                    "replay_id": 811,
                },
                {
                    "players": ["player3", "player2", "player1"],
                    "turn_count": 45,
                    "game_score": 15,
                    "replay_id": 271,
                },
                {
                    "players": ["dupe1", "dupe2", "dupe3"],
                    "turn_count": 46,
                    "game_score": 13,
                    "replay_id": 920989,
                },
                {
                    "players": ["dupe1", "dupe2", "dupe3"],
                    "turn_count": 46,
                    "game_score": 12,
                    "replay_id": 920982,
                },
                {
                    "players": ["alsodqed", "anotherplayer1", "dqed"],
                    "turn_count": 8,
                    "game_score": 1,
                    "replay_id": 798,
                },
                {
                    "players": ["dupe1", "dupe2", "dupe3"],
                    "turn_count": 28,
                    "game_score": 7,
                    "replay_id": 920998,
                },
                {
                    "players": ["dupe2", "alsodqed", "dupe3"],
                    "turn_count": 43,
                    "game_score": 11,
                    "replay_id": 921020,
                },
            ],
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert {r["replay_id"] for r in resp.json()["replays"]} == {798, 811, 812, 271}
    assert len(resp.json()["names"]) == 9
    assert HanabiReplay.objects.get(replay_id=812).spades_score == pytest.approx(6.0)
    assert HanabiReplay.objects.get(replay_id=811).spades_score == pytest.approx(5.0)
    assert HanabiReplay.objects.get(replay_id=271).spades_score == pytest.approx(
        1.265625
    )
    assert HanabiParticipation.objects.all().count() == 9
    assert HanabiParticipation.objects.filter(replay__replay_id=812).count() == 3
    assert HanabiParticipation.objects.filter(replay__replay_id=811).count() == 2
    assert HanabiParticipation.objects.filter(replay__replay_id=271).count() == 3
    assert HanabiParticipation.objects.filter(replay__replay_id=798).count() == 1
    assert set(
        HanabiParticipation.objects.all().values_list(
            "player__hanab_username", flat=True
        )
    ) == {
        "anotherplayer1",
        "player1",
        "player2",
        "player3",
        "runnerup1",
        "runnerup2",
        "winner1",
        "winner2",
        "winner3",
    }

    contest.refresh_from_db()
    assert contest.processed


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_grade_problem_set(otis):
    unit = UnitFactory.create()
    alice_user = UserFactory.create()

    pset1 = PSetFactory.create(
        student__user=alice_user,
        student__semester__active=False,
        unit=unit,
        eligible=False,
        status="A",
    )
    pset2 = PSetFactory.create(
        student__user=alice_user,
        student__semester__active=False,
        unit=unit,
        eligible=True,
        status="A",
    )
    pset3 = PSetFactory.create(student__user=alice_user, unit=unit, status="P")

    resp = otis.post_20x(
        "api",
        json={
            "pk": pset3.pk,
            "action": "grade_problem_set",
            "token": EXAMPLE_PASSWORD,
            "status": "A",
            "staff_comments": "Good job",
        },
    )
    assert resp.json()["result"] == "success"

    pset1.refresh_from_db()
    pset2.refresh_from_db()
    pset3.refresh_from_db()
    assert not pset1.eligible
    assert not pset2.eligible
    assert pset3.eligible
    assert pset1.status == "A"
    assert pset2.status == "A"
    assert pset3.status == "A"
    assert pset3.staff_comments == "Good job"


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_announcement(otis):
    assert not Announcement.objects.all().exists()

    # Create a new announcement
    resp = otis.post_20x(
        "api",
        json={
            "action": "announcement_write",
            "slug": "testing",
            "subject": "Testing 1",
            "content": "This is a sample **announcement**.",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert resp.json()["is_new"] is True
    assert Announcement.objects.all().count() == 1
    a = Announcement.objects.get(slug="testing")
    assert a.subject == "Testing 1"
    assert (
        a.content_rendered == "<p>This is a sample <strong>announcement</strong>.</p>\n"
    )

    # Update it
    resp = otis.post_20x(
        "api",
        json={
            "action": "announcement_write",
            "slug": "testing",
            "subject": "Testing 2",
            "content": "Another update.",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert resp.json()["is_new"] is False
    assert Announcement.objects.all().count() == 1
    a = Announcement.objects.get(slug="testing")
    assert a.subject == "Testing 2"
    assert a.content_rendered == "<p>Another update.</p>\n"

    # Create a third announcement
    resp = otis.post_20x(
        "api",
        json={
            "action": "announcement_write",
            "slug": "thinking",
            "subject": "Deep in thought",
            "content": "Couldn't be me!",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert resp.json()["is_new"] is True
    assert Announcement.objects.all().count() == 2
    a = Announcement.objects.get(slug="thinking")
    assert a.subject == "Deep in thought"
    assert a.content_rendered == "<p>Couldn't be me!</p>\n"


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_handler(otis):
    hunt = OpalHuntFactory.create(slug="teammate")
    OpalPuzzleFactory.create(hunt=hunt, slug="tetrogram", is_metapuzzle=True)
    resp = otis.post_20x(
        "api",
        json={
            "action": "opal_list",
            "token": EXAMPLE_PASSWORD,
        },
    )
    assert len(resp.json()["puzzles"]) == 1
    puzzle_json = resp.json()["puzzles"][0]
    assert puzzle_json["hunt__slug"] == "teammate"
    assert puzzle_json["slug"] == "tetrogram"
    assert puzzle_json["is_metapuzzle"] is True
    # A puzzle with no PDF yet reports no fingerprint, which is what tells a sync
    # to upload rather than skip.
    assert puzzle_json["content"] == ""
    assert puzzle_json["content_hash"] == ""


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_handler_reports_content_hash(otis):
    puzzle = OpalPuzzleFactory.create(hunt__slug="teammate", slug="tetrogram")
    puzzle.content.save("tetrogram.pdf", opal_pdf(b"first"), save=False)
    puzzle.content_hash = "a" * 64
    puzzle.save()

    resp = otis.post_20x(
        "api",
        json={"action": "opal_list", "token": EXAMPLE_PASSWORD},
    )
    puzzle_json = resp.json()["puzzles"][0]
    assert puzzle_json["content_hash"] == "a" * 64
    assert puzzle_json["content"].endswith("tetrogram.pdf")


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_apply_uuid_handler(otis):
    otis.post_20x(
        "api",
        json={
            "action": "apply_uuid",
            "token": EXAMPLE_PASSWORD,
            "uuid": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",  # no that's not a diamond
            "percent_aid": 50,
            "applicant_name": "Alice Applicant",
        },
    )
    assert (
        ApplyUUID.objects.filter(
            uuid="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
            percent_aid=50,
            applicant_name="Alice Applicant",
        ).count()
        == 1
    )


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_pdf_upload(otis):
    puzzle = OpalPuzzleFactory.create(hunt__slug="teammate", slug="tetrogram")
    assert puzzle.content_hash == ""

    resp = otis.post_20x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": puzzle.pk,
            "content": opal_pdf(b"first draft"),
        },
    )
    assert resp.json()["status"] == "created"
    puzzle.refresh_from_db()
    assert puzzle.content.read() == b"%PDF-1.4 first draft"
    assert puzzle.content.name.startswith("opals/teammate/")
    assert puzzle.content.name.endswith("/tetrogram.pdf")
    assert puzzle.content_hash == sha256(b"%PDF-1.4 first draft").hexdigest()
    assert resp.json()["content_hash"] == puzzle.content_hash

    first_name = puzzle.content.name

    # Same bytes again: the server should recognize them and leave storage alone.
    resp = otis.post_20x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": puzzle.pk,
            "content": opal_pdf(b"first draft"),
        },
    )
    assert resp.json()["status"] == "unchanged"
    puzzle.refresh_from_db()
    assert puzzle.content.name == first_name

    # Different bytes: rewritten in place, with no suffixed duplicate left behind.
    resp = otis.post_20x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": puzzle.pk,
            "content": opal_pdf(b"second draft"),
        },
    )
    assert resp.json()["status"] == "updated"
    puzzle.refresh_from_db()
    assert puzzle.content.name == first_name
    assert puzzle.content.read() == b"%PDF-1.4 second draft"
    assert puzzle.content_hash == sha256(b"%PDF-1.4 second draft").hexdigest()


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_pdf_upload_renamed_file_leaves_no_orphan(otis):
    puzzle = OpalPuzzleFactory.create(hunt__slug="teammate", slug="tetrogram")
    otis.post_20x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": puzzle.pk,
            "content": SimpleUploadedFile("old_name.pdf", b"%PDF-1.4 draft"),
        },
    )
    puzzle.refresh_from_db()
    old_name = puzzle.content.name
    assert puzzle.content.storage.exists(old_name)

    otis.post_20x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": puzzle.pk,
            "content": SimpleUploadedFile("tetrogram.pdf", b"%PDF-1.4 draft"),
        },
    )
    puzzle.refresh_from_db()
    assert puzzle.content.name.endswith("tetrogram.pdf")
    assert not puzzle.content.storage.exists(old_name)


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
@pytest.mark.parametrize(
    "upload",
    (
        SimpleUploadedFile("tetrogram.tex", b"%PDF-1.4 not really"),
        SimpleUploadedFile("tetrogram.pdf", b"\\documentclass{article}"),
    ),
    ids=("wrong extension", "wrong bytes"),
)
def test_opal_pdf_upload_rejects_non_pdf(otis, upload: SimpleUploadedFile):
    puzzle = OpalPuzzleFactory.create(hunt__slug="teammate", slug="tetrogram")
    otis.post_40x(
        "opal-pdf-upload",
        data={"token": EXAMPLE_PASSWORD, "pk": puzzle.pk, "content": upload},
    )
    puzzle.refresh_from_db()
    assert not puzzle.content
    assert puzzle.content_hash == ""


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_pdf_upload_failed_auth(otis):
    puzzle = OpalPuzzleFactory.create(hunt__slug="teammate", slug="tetrogram")
    resp = otis.post_40x(
        "opal-pdf-upload",
        data={
            "token": "this wrong password is not a puzzle",
            "pk": puzzle.pk,
            "content": opal_pdf(b"first draft"),
        },
    )
    assert resp.status_code == 418
    puzzle.refresh_from_db()
    assert not puzzle.content


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
def test_opal_pdf_upload_unknown_puzzle(otis):
    otis.post_not_found(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": 1729,
            "content": opal_pdf(b"first draft"),
        },
    )
    assert not OpalPuzzle.objects.exists()


@pytest.mark.django_db
@override_settings(API_TARGET_HASH=TARGET_HASH)
@pytest.mark.parametrize("pk", ("", "tetrogram"), ids=("empty", "not a number"))
def test_opal_pdf_upload_malformed_pk(otis, pk: str):
    otis.post_40x(
        "opal-pdf-upload",
        data={
            "token": EXAMPLE_PASSWORD,
            "pk": pk,
            "content": opal_pdf(b"first draft"),
        },
    )
