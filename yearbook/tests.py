import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.factories import GroupFactory, SemesterFactory, UserFactory
from roster.country_abbrevs import get_country_flag, get_country_name
from roster.factories import StudentFactory
from yearbook.factories import YearbookEntryFactory
from yearbook.models import YearbookEntry


def test_country_flag():
    assert get_country_flag("USA") == "🇺🇸"
    assert get_country_flag("UNK") == "🇬🇧"  # IMO calls the UK "UNK", ISO says "GB"
    assert get_country_flag("HEL") == "🇬🇷"  # ditto Greece, "HEL" versus "GR"
    assert get_country_flag("") == ""
    assert get_country_flag("YUG") == "🌐"  # no flag emoji for defunct countries
    assert get_country_name("SAF") == "South Africa"
    assert get_country_name("bogus") == "bogus"


@pytest.mark.django_db
def test_yearbook_requires_verified(otis):
    otis.get_login_redirect("yearbook-list")
    otis.get_login_redirect("yearbook-create")

    rando: User = UserFactory(username="rando")
    entry = YearbookEntryFactory(tagline="just another otter")

    otis.login(rando)
    otis.get_denied("yearbook-list")
    otis.get_denied("yearbook-create")
    otis.get_denied("yearbook-detail", entry.user.username)


@pytest.mark.django_db
def test_yearbook_listing(otis):
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory(
        username="alice", first_name="Alice", last_name="Aardvark",
        groups=(verified_group,),
    )
    YearbookEntryFactory(
        user=alice,
        tagline="just another otter",
        country="AUS",
        graduation_year=2026,
    )
    otis.login(alice)

    resp = otis.get_20x("yearbook-list")
    otis.assert_has(resp, "Alice Aardvark")
    otis.assert_has(resp, "just another otter")
    otis.assert_has(resp, "Class of 2026")
    otis.assert_has(resp, "🇦🇺")
    otis.assert_has(resp, 'aria-label="Australia"')
    # already signed, so no policy warning and no invitation to sign
    otis.assert_not_has(resp, "Before you sign the yearbook")


@pytest.mark.django_db
def test_yearbook_listing_warns_before_signing(otis):
    verified_group = GroupFactory(name="Verified")
    bob: User = UserFactory(
        username="bob", first_name="Bob", last_name="Bobson", groups=(verified_group,)
    )
    otis.login(bob)

    resp = otis.get_20x("yearbook-list")
    otis.assert_has(resp, "Before you sign the yearbook")
    otis.assert_has(resp, "The yearbook uses real names")
    otis.assert_has(resp, "Your years in OTIS are shown")
    otis.assert_has(resp, "Bob Bobson")
    otis.assert_has(resp, "Nobody has signed the yearbook yet")


@pytest.mark.django_db
def test_yearbook_detail(otis):
    verified_group = GroupFactory(name="Verified")
    carol: User = UserFactory(
        username="carol", first_name="Carol", last_name="Carolson",
        groups=(verified_group,),
    )
    StudentFactory(user=carol, semester=SemesterFactory(name="Year I", end_year=2023))
    StudentFactory(user=carol, semester=SemesterFactory(name="Year II", end_year=2024))
    YearbookEntryFactory(
        user=carol,
        tagline="fond of ducks",
        country="CAN",
        graduation_year=2024,
        email="carol@example.com",
        discord_username="carolduck",
        github_username="carol-hub",
        aops_username="carol_aops",
        instagram_username="carolgram",
        imo_years="2023, 2022",
        university="Duck University",
        bio="I like **ducks** a lot.",
    )
    otis.login(carol)

    resp = otis.get_20x("yearbook-detail", "carol")
    otis.assert_has(resp, "Carol Carolson")
    otis.assert_has(resp, "fond of ducks")
    otis.assert_has(resp, "🇨🇦")
    otis.assert_has(resp, "Class of 2024")
    otis.assert_has(resp, "Duck University")
    otis.assert_has(resp, "carol@example.com")
    otis.assert_has(resp, "carolduck")
    otis.assert_has(resp, "https://github.com/carol-hub")
    otis.assert_has(resp, "carol_aops")
    otis.assert_has(resp, "https://www.instagram.com/carolgram/")
    otis.assert_has(resp, "I like <strong>ducks</strong> a lot.")
    # years in OTIS come off the roster, not from anything the student typed
    otis.assert_has(resp, "Year I (2022-2023)")
    otis.assert_has(resp, "Year II (2023-2024)")
    # IMO years get sorted on the way in
    otis.assert_has(resp, "2022")
    assert YearbookEntry.objects.get(user=carol).imo_year_list == [2022, 2023]

    otis.get_not_found("yearbook-detail", "nonexistent")


@pytest.mark.django_db
def test_yearbook_detail_hides_blank_fields(otis):
    verified_group = GroupFactory(name="Verified")
    dave: User = UserFactory(username="dave", groups=(verified_group,))
    YearbookEntryFactory(
        user=dave, tagline="", country="", graduation_year=None, university="", bio=""
    )
    otis.login(dave)

    resp = otis.get_20x("yearbook-detail", "dave")
    otis.assert_has(resp, "has not written anything here yet")
    otis.assert_has(resp, "No student enrollments on record")
    otis.assert_not_has(resp, "Elsewhere")
    otis.assert_not_has(resp, "University")


@pytest.mark.django_db
def test_yearbook_create(otis):
    verified_group = GroupFactory(name="Verified")
    erin: User = UserFactory(
        username="erin", first_name="Erin", last_name="Erinson",
        email="erin@example.com", groups=(verified_group,),
    )
    otis.login(erin)

    resp = otis.get_20x("yearbook-create")
    otis.assert_has(resp, "Before you sign the yearbook")
    otis.assert_has(resp, "I understand the yearbook policy")
    # the create form is prefilled with the account email
    otis.assert_has(resp, "erin@example.com")

    # refusing to acknowledge the policy blocks the entry
    otis.post_20x(
        "yearbook-create", data={"tagline": "no thanks", "bio": "", "imo_years": ""}
    )
    assert not YearbookEntry.objects.filter(user=erin).exists()

    resp = otis.post_30x(
        "yearbook-create",
        data={
            "acknowledge": "on",
            "tagline": "just another otter",
            "country": "USA",
            "graduation_year": 2027,
            "email": "erin@example.com",
            "imo_years": "2024, 2023, 2024",
            "university": "Otter Tech",
            "bio": "Hello!",
        },
    )
    entry = YearbookEntry.objects.get(user=erin)
    assert entry.tagline == "just another otter"
    assert entry.country_name == "United States of America"
    # duplicate years are collapsed and the list is sorted
    assert entry.imo_years == "2023, 2024"
    otis.assert_redirects(resp, entry.get_absolute_url())

    # a second attempt to sign sends you to the edit form instead
    resp = otis.get_30x("yearbook-create")
    otis.assert_redirects(resp, otis.url("yearbook-update"))


@pytest.mark.django_db
def test_yearbook_create_rejects_bad_input(otis):
    verified_group = GroupFactory(name="Verified")
    frank: User = UserFactory(username="frank", groups=(verified_group,))
    otis.login(frank)

    otis.post_20x(
        "yearbook-create",
        data={"acknowledge": "on", "imo_years": "twenty twenty three"},
    )
    otis.post_20x(
        "yearbook-create",
        data={"acknowledge": "on", "imo_years": "1066"},
    )
    otis.post_20x(
        "yearbook-create",
        data={"acknowledge": "on", "github_username": "not a username"},
    )
    assert not YearbookEntry.objects.filter(user=frank).exists()


@pytest.mark.django_db
def test_yearbook_update_and_delete(otis):
    verified_group = GroupFactory(name="Verified")
    gina: User = UserFactory(username="gina", groups=(verified_group,))
    hank: User = UserFactory(username="hank", groups=(verified_group,))
    YearbookEntryFactory(user=gina, tagline="before")
    otis.login(gina)

    otis.assert_has(otis.get_20x("yearbook-update"), "before")
    otis.post_30x(
        "yearbook-update",
        data={"tagline": "after", "imo_years": "", "bio": ""},
    )
    assert YearbookEntry.objects.get(user=gina).tagline == "after"

    # somebody without an entry has nothing to edit or delete
    otis.login(hank)
    otis.get_not_found("yearbook-update")
    otis.get_not_found("yearbook-delete")

    otis.login(gina)
    otis.assert_has(otis.get_20x("yearbook-delete"), "leave the yearbook")
    otis.post_30x("yearbook-delete")
    assert not YearbookEntry.objects.filter(user=gina).exists()


@pytest.mark.django_db
def test_yearbook_entry_model():
    user: User = UserFactory(username="ivy", first_name="", last_name="")
    entry = YearbookEntryFactory(user=user, country="")
    # falls back to the username when the account has no real name on it
    assert entry.name == "ivy"
    assert entry.country_flag == ""
    assert entry.country_name == ""
    assert entry.otis_years is None
    assert str(entry) == "Yearbook entry for ivy"

    StudentFactory(user=user, semester=SemesterFactory(name="Year I", end_year=2023))
    StudentFactory(user=user, semester=SemesterFactory(name="Year III", end_year=2025))
    assert entry.otis_years == "2022-2025"

    entry.imo_years = "2020"
    entry.full_clean(exclude=("bio_rendered",))
    entry.imo_years = "2020, notayear"
    with pytest.raises(ValidationError):
        entry.full_clean(exclude=("bio_rendered",))
