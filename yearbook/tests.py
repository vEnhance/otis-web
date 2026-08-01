import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.factories import GroupFactory, SemesterFactory, UserFactory
from roster.country_abbrevs import (
    get_country_flag,
    get_country_imo_url,
    get_country_name,
)
from roster.factories import StudentFactory
from yearbook.factories import YearbookEntryFactory
from yearbook.models import YearbookEntry


def test_country_flag():
    assert get_country_flag("USA") == "🇺🇸"
    assert get_country_flag("UNK") == "🇬🇧"  # IMO calls the UK "UNK", ISO says "GB"
    assert get_country_flag("") == ""
    assert get_country_flag("YUG") == "🌐"  # no flag emoji for defunct countries
    assert get_country_name("SAF") == "South Africa"
    assert get_country_name("bogus") == "bogus"


def test_country_imo_url():
    assert (
        get_country_imo_url("CHN")
        == "https://www.imo-official.org/results/team/country/CHN/"
    )
    # the IMO keeps results pages for countries that no longer exist
    assert (
        get_country_imo_url("USS")
        == "https://www.imo-official.org/results/team/country/USS/"
    )
    assert get_country_imo_url("") == ""
    assert get_country_imo_url("bogus") == ""


@pytest.mark.django_db
def test_yearbook_requires_verified(otis):
    otis.get_login_redirect("yearbook-list")
    otis.get_login_redirect("yearbook-create")

    rando: User = UserFactory(username="rando")
    entry = YearbookEntryFactory(tagline="just another otter")

    otis.login(rando)
    otis.get_denied("yearbook-list")
    otis.get_denied("yearbook-create")
    otis.get_denied("yearbook-detail", entry.pk)


@pytest.mark.django_db
def test_yearbook_listing(otis):
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory(
        username="alice",
        first_name="Alice",
        last_name="Aardvark",
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
    # the policy warning lives on the create form, not on the listing
    otis.assert_not_has(resp, "requires real names")


@pytest.mark.django_db
def test_yearbook_detail(otis):
    verified_group = GroupFactory(name="Verified")
    carol: User = UserFactory(
        username="carol",
        first_name="Carol",
        last_name="Carolson",
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

    entry = YearbookEntry.objects.get(user=carol)
    resp = otis.get_20x("yearbook-detail", entry.pk)
    otis.assert_has(resp, "Carol Carolson")
    otis.assert_has(resp, "fond of ducks")
    otis.assert_has(resp, "🇨🇦")
    # the country shows as its IMO abbreviation, linked to the IMO results page
    otis.assert_has(resp, "https://www.imo-official.org/results/team/country/CAN/")
    otis.assert_has(resp, 'title="Canada at the IMO"')
    otis.assert_has(resp, "Class of")  # the infobox row label; 2024 is the value
    otis.assert_has(resp, "Duck University")
    otis.assert_has(resp, "carol@example.com")
    otis.assert_has(resp, "carolduck")
    otis.assert_has(resp, "https://github.com/carol-hub")
    otis.assert_has(resp, "carol_aops")
    otis.assert_has(resp, "https://www.instagram.com/carolgram/")
    otis.assert_has(resp, "I like <strong>ducks</strong> a lot.")
    # years in OTIS come off the roster, not from anything the student typed,
    # and show as the end year of each semester
    otis.assert_has(resp, "2023,")
    otis.assert_has(resp, "2024")
    otis.assert_not_has(resp, "Year I")
    # IMO years get sorted on the way in
    otis.assert_has(resp, "2022")
    assert YearbookEntry.objects.get(user=carol).imo_year_list == [2022, 2023]

    otis.get_not_found("yearbook-detail", entry.pk + 1000)


@pytest.mark.django_db
def test_yearbook_detail_hides_blank_fields(otis):
    verified_group = GroupFactory(name="Verified")
    dave: User = UserFactory(username="dave", groups=(verified_group,))
    entry = YearbookEntryFactory(
        user=dave, tagline="", country="", graduation_year=None, university="", bio=""
    )
    otis.login(dave)

    resp = otis.get_20x("yearbook-detail", entry.pk)
    otis.assert_has(resp, "has not written anything here yet")
    otis.assert_has(resp, "No student enrollments on record")
    otis.assert_not_has(resp, "Elsewhere")
    otis.assert_not_has(resp, "University")


@pytest.mark.django_db
def test_yearbook_create(otis):
    verified_group = GroupFactory(name="Verified")
    erin: User = UserFactory(
        username="erin",
        first_name="Erin",
        last_name="Erinson",
        email="erin@example.com",
        groups=(verified_group,),
    )
    otis.login(erin)

    resp = otis.get_20x("yearbook-create")
    otis.assert_has(resp, "requires real names")
    # the create form is prefilled with the account email
    otis.assert_has(resp, "erin@example.com")
    # the form is grouped into sections
    otis.assert_has(resp, "<h2>Biographical data</h2>")
    otis.assert_has(resp, "<h2>Contact</h2>")
    # contact accounts are a compact table of short labels, with no help text
    otis.assert_has(resp, "yearbook-contact-table")
    otis.assert_has(resp, '<label for="id_discord_username">Discord</label>')
    # ...whereas the biographical table keeps its help text
    otis.assert_has(resp, "yearbook-bio-table")
    otis.assert_has(resp, "The university you attend or attended")
    otis.assert_not_has(resp, "Your Discord handle")
    # the country picker is a chosen-style autocomplete, as on the decision form
    otis.assert_has(resp, 'id="id_country"')
    otis.assert_has(resp, '$("#id_country").chosen(')

    resp = otis.post_30x(
        "yearbook-create",
        data={
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
        data={"imo_years": "twenty twenty three"},
    )
    otis.post_20x(
        "yearbook-create",
        data={"imo_years": "1066"},
    )
    otis.post_20x(
        "yearbook-create",
        data={"github_username": "not a username"},
    )
    # pasting a handle with its @ would silently break the profile links
    resp = otis.post_20x(
        "yearbook-create",
        data={"instagram_username": "@evanchen.cc"},
    )
    otis.assert_has(resp, "without the leading @")
    assert not YearbookEntry.objects.filter(user=frank).exists()


@pytest.mark.django_db
def test_yearbook_drafts_are_hidden(otis):
    verified_group = GroupFactory(name="Verified")
    iris: User = UserFactory(
        username="iris",
        first_name="Iris",
        last_name="Irisson",
        groups=(verified_group,),
    )
    nosy: User = UserFactory(username="nosy", groups=(verified_group,))
    staffer: User = UserFactory(username="staffer", is_staff=True)
    draft = YearbookEntryFactory(user=iris, tagline="not ready yet", is_draft=True)

    # a nosy classmate sees neither the card nor the page
    otis.login(nosy)
    otis.assert_not_has(otis.get_20x("yearbook-list"), "Iris Irisson")
    otis.get_not_found("yearbook-detail", draft.pk)

    # the author sees their own draft, flagged as such
    otis.login(iris)
    resp = otis.get_20x("yearbook-list")
    otis.assert_has(resp, "Iris Irisson")
    otis.assert_has(resp, "Draft")
    resp = otis.get_20x("yearbook-detail", draft.pk)
    otis.assert_has(resp, "This entry is a draft")
    otis.assert_has(resp, "not ready yet")

    # so does staff
    otis.login(staffer)
    otis.assert_has(otis.get_20x("yearbook-list"), "Iris Irisson")
    otis.assert_has(otis.get_20x("yearbook-detail", draft.pk), "This entry is a draft")

    # publishing makes it visible to everyone
    otis.login(iris)
    otis.post_30x("yearbook-update", data={"tagline": "ready now", "imo_years": ""})
    assert YearbookEntry.objects.get(user=iris).is_draft is False
    otis.login(nosy)
    resp = otis.get_20x("yearbook-list")
    otis.assert_has(resp, "Iris Irisson")
    otis.assert_not_has(resp, "Draft")
    otis.assert_has(otis.get_20x("yearbook-detail", draft.pk), "ready now")


@pytest.mark.django_db
def test_yearbook_create_as_draft(otis):
    verified_group = GroupFactory(name="Verified")
    jack: User = UserFactory(username="jack", groups=(verified_group,))
    otis.login(jack)

    # entries are published by default; draft mode is opt-in
    otis.post_30x("yearbook-create", data={"tagline": "hello", "imo_years": ""})
    assert YearbookEntry.objects.get(user=jack).is_draft is False

    otis.post_30x(
        "yearbook-update",
        data={"tagline": "hello", "imo_years": "", "is_draft": "on"},
    )
    assert YearbookEntry.objects.get(user=jack).is_draft is True


@pytest.mark.django_db
def test_yearbook_update(otis):
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

    # somebody without an entry has nothing to edit
    otis.login(hank)
    otis.get_not_found("yearbook-update")


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
