import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from freezegun.api import freeze_time

from core.factories import GroupFactory, SemesterFactory, UserFactory
from roster.country_abbrevs import (
    get_country_flag,
    get_country_imo_url,
    get_country_name,
)
from roster.factories import StudentFactory
from yearbook.factories import YearbookEntryFactory
from yearbook.models import YearbookEntry
from yearbook.views import ENTRIES_PER_PAGE, NUM_RANDOM_ENTRIES


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
    otis.get_login_redirect("yearbook-index")
    otis.get_login_redirect("yearbook-list")
    otis.get_login_redirect("yearbook-jump")
    otis.get_login_redirect("yearbook-create")

    rando: User = UserFactory(username="rando")
    entry = YearbookEntryFactory(tagline="just another otter")

    otis.login(rando)
    otis.get_denied("yearbook-index")
    otis.get_denied("yearbook-list")
    otis.get_denied("yearbook-jump")
    otis.get_denied("yearbook-create")
    otis.get_denied("yearbook-detail", entry.pk)


@pytest.mark.django_db
def test_yearbook_list_shows_cards(otis):
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
    otis.assert_has(resp, "’26")
    otis.assert_has(resp, "🇦🇺")
    otis.assert_has(resp, 'aria-label="Australia"')
    # the policy warning lives on the create form, not on the listing
    otis.assert_no_testid(resp, "yearbook-real-names-warning")


@pytest.mark.django_db
def test_yearbook_list_paginates(otis):
    verified_group = GroupFactory(name="Verified")
    zoe: User = UserFactory(
        username="zoe", first_name="Zoe", last_name="Zebra", groups=(verified_group,)
    )
    zoe_entry = YearbookEntryFactory(user=zoe)
    for i in range(24):
        YearbookEntryFactory(
            user=UserFactory(
                username=f"otter{i:02d}",
                first_name=f"Otter{i:02d}",
                last_name="Otterson",
            )
        )
    otis.login(zoe)

    resp = otis.get_20x("yearbook-list")
    assert resp.context["paginator"].count == 25
    assert len(resp.context["entries"]) == ENTRIES_PER_PAGE
    assert resp.context["page_obj"].number == 1

    resp = otis.get_20x("yearbook-list", data={"page": 2})
    assert len(resp.context["entries"]) == 25 - ENTRIES_PER_PAGE
    # the list is alphabetical, so Zoe Zebra is on the last page
    assert zoe_entry in resp.context["entries"]


@pytest.mark.django_db
def test_yearbook_jump(otis):
    verified_group = GroupFactory(name="Verified")
    reader: User = UserFactory(username="reader", groups=(verified_group,))
    shy: User = UserFactory(username="shy", groups=(verified_group,))
    entry = YearbookEntryFactory()
    draft = YearbookEntryFactory(user=shy, is_draft=True)
    otis.login(reader)

    resp = otis.get_30x("yearbook-jump", data={"pk": entry.pk})
    otis.assert_redirects(resp, entry.get_absolute_url())

    # submitting the picker without picking anybody stays on the index
    index_url = otis.url("yearbook-index")
    otis.assert_redirects(otis.get_30x("yearbook-jump"), index_url)
    otis.assert_redirects(otis.get_30x("yearbook-jump", data={"pk": ""}), index_url)
    otis.assert_redirects(
        otis.get_30x("yearbook-jump", data={"pk": "otter"}), index_url
    )

    # the picker is no way around the draft rules
    otis.get_not_found("yearbook-jump", data={"pk": draft.pk})
    otis.get_not_found("yearbook-jump", data={"pk": draft.pk + 1000})


@pytest.mark.django_db
def test_yearbook_index(otis):
    verified_group = GroupFactory(name="Verified")
    alice: User = UserFactory(
        username="alice",
        first_name="Alice",
        last_name="Aardvark",
        groups=(verified_group,),
    )
    bob: User = UserFactory(
        username="bob", first_name="Bob", last_name="Bobson", groups=(verified_group,)
    )
    gm: User = UserFactory(
        username="gm", first_name="Game", last_name="Master", is_superuser=True
    )
    alice_entry = YearbookEntryFactory(user=alice, tagline="just another otter")
    bob_entry = YearbookEntryFactory(user=bob)
    gm_entry = YearbookEntryFactory(user=gm)
    otis.login(alice)

    resp = otis.get_20x("yearbook-index")
    assert resp.context["num_entries"] == 3
    # the picker offers every entry this person may open
    assert set(resp.context["all_entries"]) == {alice_entry, bob_entry, gm_entry}
    otis.assert_testid(resp, "yearbook-jump")
    # the viewer's own entry gets a section of its own, as a single card
    assert resp.context["own_entry"] == alice_entry
    assert resp.context["own_entries"] == [alice_entry]
    otis.assert_no_testid(resp, "yearbook-no-own-entry")
    # so do the game masters
    assert resp.context["gm_entries"] == [gm_entry]
    # the index is a way in, not the whole yearbook: the full list lives
    # behind its own paginated page
    otis.assert_has(resp, otis.url("yearbook-list"))


@pytest.mark.django_db
def test_yearbook_index_without_own_entry(otis):
    verified_group = GroupFactory(name="Verified")
    nemo: User = UserFactory(username="nemo", groups=(verified_group,))
    YearbookEntryFactory()
    otis.login(nemo)

    resp = otis.get_20x("yearbook-index")
    assert resp.context["own_entry"] is None
    assert resp.context["own_entries"] == []
    otis.assert_testid(resp, "yearbook-no-own-entry")


@pytest.mark.django_db
def test_yearbook_index_random_entries_of_the_day(otis):
    verified_group = GroupFactory(name="Verified")
    olive: User = UserFactory(username="olive", groups=(verified_group,))
    with freeze_time("2026-08-18 12:00:00"):
        for i in range(20):
            YearbookEntryFactory(
                user=UserFactory(
                    username=f"otter{i:02d}",
                    first_name=f"Otter{i:02d}",
                    last_name="Otterson",
                )
            )

    with freeze_time("2026-08-19 23:30:00"):
        otis.login(olive)
        sample = otis.get_20x("yearbook-index").context["random_entries"]
        assert len(sample) == NUM_RANDOM_ENTRIES
        # the sample holds still rather than reshuffling on every page load
        assert otis.get_20x("yearbook-index").context["random_entries"] == sample

        # signing the yearbook today doesn't reshuffle today's five; the new
        # entry becomes eligible tomorrow
        newcomer = YearbookEntryFactory(
            user=UserFactory(username="newbie", first_name="New", last_name="Comer")
        )
        resp = otis.get_20x("yearbook-index")
        assert newcomer not in resp.context["random_entries"]
        assert resp.context["random_entries"] == sample

        # taking your entry out of the yearbook doesn't reshuffle it either:
        # it is skipped over, and the other four stay where they are
        dropped = sample[0]
        dropped.is_draft = True
        dropped.save()
        new_sample = otis.get_20x("yearbook-index").context["random_entries"]
        assert dropped not in new_sample
        assert len(new_sample) == NUM_RANDOM_ENTRIES
        assert set(sample[1:]) < set(new_sample)

    # ...and it rolls over at 0:00 UTC, not at local midnight
    with freeze_time("2026-08-20 00:30:00"):
        otis.login(olive)
        assert otis.get_20x("yearbook-index").context["random_entries"] != sample


@pytest.mark.django_db
def test_yearbook_index_never_features_drafts(otis):
    verified_group = GroupFactory(name="Verified")
    quinn: User = UserFactory(username="quinn", groups=(verified_group,))
    staffer: User = UserFactory(username="staffer", is_staff=True)
    shy_gm: User = UserFactory(username="shygm", is_superuser=True)
    with freeze_time("2026-08-18 12:00:00"):
        published = YearbookEntryFactory()
        own_draft = YearbookEntryFactory(user=quinn, is_draft=True)
        gm_draft = YearbookEntryFactory(user=shy_gm, is_draft=True)

    with freeze_time("2026-08-19 12:00:00"):
        # your own draft is yours to see, but it is not shown off to anybody
        otis.login(quinn)
        resp = otis.get_20x("yearbook-index")
        assert resp.context["own_entry"] == own_draft
        assert resp.context["random_entries"] == [published]
        assert resp.context["gm_entries"] == []

        # not even staff, who can see the drafts everywhere else
        otis.login(staffer)
        resp = otis.get_20x("yearbook-index")
        assert own_draft in resp.context["all_entries"]
        assert gm_draft in resp.context["all_entries"]
        assert resp.context["random_entries"] == [published]
        assert resp.context["gm_entries"] == []


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
        imo_id=24870,
        website="https://ducks.example.com/carol/",
        university="Duck University",
        bio="I like **ducks** a lot.",
    )
    otis.login(carol)

    entry = YearbookEntry.objects.get(user=carol)
    resp = otis.get_20x("yearbook-detail", entry.pk)
    # A profile page exists to put this person's own data on the screen, so the
    # rendered values are the contract here. These assertions are on model data
    # and links, never on the page's own wording.
    otis.assert_has(resp, "Carol Carolson")
    otis.assert_has(resp, "fond of ducks")
    otis.assert_has(resp, "🇨🇦")
    # the country shows as its IMO abbreviation, linked to the IMO results page
    otis.assert_has(resp, "https://www.imo-official.org/results/team/country/CAN/")
    otis.assert_has(resp, 'title="Canada at the IMO"')
    otis.assert_testid(resp, "yearbook-class-of-row")
    assert resp.context["entry"].graduation_year == 2024
    otis.assert_has(resp, "Duck University")
    otis.assert_has(resp, "carol@example.com")
    # socials are icon rows, with the account type in the icon's alt text
    otis.assert_has(resp, "carolduck")
    otis.assert_has(resp, 'alt="Discord"')
    otis.assert_has(resp, "yearbook/icons/discord.svg")
    otis.assert_has(resp, "yearbook/icons/aops.png")
    otis.assert_has(resp, "https://github.com/carol-hub")
    otis.assert_has(resp, "https://artofproblemsolving.com/community/user/carol_aops")
    otis.assert_has(resp, "https://www.instagram.com/carolgram/")
    otis.assert_has(resp, "I like <strong>ducks</strong> a lot.")
    # years in OTIS come off the roster, not from anything the student typed,
    # and collapse to a range rather than showing the semester names
    assert resp.context["entry"].otis_years == "2022-2024"
    # the IMO ID links to that contestant's page on the IMO site
    otis.assert_has(resp, "https://www.imo-official.org/results/contestant/24870/")
    otis.assert_has(resp, "24870")
    # the website is shown without its scheme, which is noise in the infobox
    otis.assert_has(resp, 'href="https://ducks.example.com/carol/"')
    otis.assert_has(resp, "ducks.example.com/carol")

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
    otis.assert_testid(resp, "yearbook-empty-bio")
    otis.assert_testid(resp, "yearbook-no-contact")
    otis.assert_no_testid(resp, "yearbook-infobox-social")
    otis.assert_no_testid(resp, "yearbook-university-row")
    otis.assert_no_testid(resp, "yearbook-class-of-row")


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
    otis.assert_testid(resp, "yearbook-real-names-warning")
    form = resp.context["form"]
    # the create form is prefilled with the account email
    assert form.initial["email"] == "erin@example.com"
    # the form is grouped into sections
    otis.assert_testid(resp, "yearbook-bio-table")
    otis.assert_testid(resp, "yearbook-contact-heading")
    otis.assert_testid(resp, "yearbook-contact-table")
    # contact accounts get short labels and no help text...
    assert form.fields["discord_username"].label == "Discord"
    assert not form.fields["discord_username"].help_text
    # ...whereas the biographical fields keep theirs (the wording is Evan's to
    # change; what matters is that one table has help text and the other doesn't)
    assert form.fields["university"].help_text
    # the country picker is a chosen-style autocomplete, as on the decision form
    assert "country" in form.fields
    otis.assert_has(resp, '$("#id_country").chosen(')

    resp = otis.post_30x(
        "yearbook-create",
        data={
            "tagline": "just another otter",
            "country": "USA",
            "graduation_year": 2027,
            "email": "erin@example.com",
            "imo_id": 24870,
            "website": "https://otters.example.com",
            "university": "Otter Tech",
            "bio": "Hello!",
        },
    )
    entry = YearbookEntry.objects.get(user=erin)
    assert entry.tagline == "just another otter"
    assert entry.country_name == "United States of America"
    assert entry.imo_id == 24870
    assert entry.imo_url == "https://www.imo-official.org/results/contestant/24870/"
    assert entry.website_display == "otters.example.com"
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
        data={"imo_id": "not a number"},
    )
    otis.post_20x(
        "yearbook-create",
        data={"imo_id": -5},
    )
    otis.post_20x(
        "yearbook-create",
        data={"website": "not a url"},
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
    assert "instagram_username" in resp.context["form"].errors
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
    assert draft not in otis.get_20x("yearbook-list").context["entries"]
    otis.get_not_found("yearbook-detail", draft.pk)

    # the author sees their own draft, flagged as such
    otis.login(iris)
    resp = otis.get_20x("yearbook-list")
    assert draft in resp.context["entries"]
    otis.assert_testid(resp, "yearbook-draft-badge")
    resp = otis.get_20x("yearbook-detail", draft.pk)
    otis.assert_testid(resp, "yearbook-draft-note")
    assert resp.context["entry"].tagline == "not ready yet"

    # so does staff
    otis.login(staffer)
    assert draft in otis.get_20x("yearbook-list").context["entries"]
    otis.assert_testid(otis.get_20x("yearbook-detail", draft.pk), "yearbook-draft-note")

    # publishing makes it visible to everyone
    otis.login(iris)
    otis.post_30x("yearbook-update", data={"tagline": "ready now"})
    assert YearbookEntry.objects.get(user=iris).is_draft is False
    otis.login(nosy)
    resp = otis.get_20x("yearbook-list")
    assert draft in resp.context["entries"]
    otis.assert_no_testid(resp, "yearbook-draft-badge")
    assert otis.get_20x("yearbook-detail", draft.pk).context["entry"].tagline == (
        "ready now"
    )


@pytest.mark.django_db
def test_yearbook_create_as_draft(otis):
    verified_group = GroupFactory(name="Verified")
    jack: User = UserFactory(username="jack", groups=(verified_group,))
    otis.login(jack)

    # entries are published by default; draft mode is opt-in
    otis.post_30x("yearbook-create", data={"tagline": "hello"})
    assert YearbookEntry.objects.get(user=jack).is_draft is False

    otis.post_30x(
        "yearbook-update",
        data={"tagline": "hello", "is_draft": "on"},
    )
    assert YearbookEntry.objects.get(user=jack).is_draft is True


@pytest.mark.django_db
def test_yearbook_update(otis):
    verified_group = GroupFactory(name="Verified")
    gina: User = UserFactory(username="gina", groups=(verified_group,))
    hank: User = UserFactory(username="hank", groups=(verified_group,))
    YearbookEntryFactory(user=gina, tagline="before")
    otis.login(gina)

    assert otis.get_20x("yearbook-update").context["form"].initial["tagline"] == (
        "before"
    )
    otis.post_30x(
        "yearbook-update",
        data={"tagline": "after", "bio": ""},
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

    # no IMO ID and no website means nothing to link to
    assert entry.imo_url == ""
    assert entry.website_display == ""

    entry.discord_username = "@ivy"
    with pytest.raises(ValidationError):
        entry.full_clean(exclude=("bio_rendered",))
