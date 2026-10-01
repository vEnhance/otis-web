import pytest
from django.contrib.auth.models import Group, User
from django.contrib.messages import constants as message_levels

from core.factories import UserFactory
from roster.factories import AssistantFactory, AssistantListingFactory
from roster.models import Assistant, AssistantListing

LISTING_DATA = {
    "enabled": True,
    "offers_one_on_one": True,
    "offers_group": False,
    "time_zone": "Asia/Kolkata",
    "availability": "weekend evenings",
    "website": "https://evanchen.cc/",
    "email": "overlord@evanchen.cc",
    "syllabus_url": "https://evanchen.cc/syllabus.pdf",
    "example_url": "https://evanchen.cc/example.pdf",
    "next_steps": "Fill out the form on my website.",
    "blurb": "I'm an ovie!",
}


def verified_user(**kwargs: bool) -> User:
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    return UserFactory.create(groups=(verified_group,), **kwargs)


def verified_assistant() -> Assistant:
    return AssistantFactory.create(user=verified_user(is_staff=True))


@pytest.mark.django_db
def test_ad_list_requires_verified(otis) -> None:
    otis.get_30x("ad-list")
    otis.login(UserFactory.create())
    otis.get_40x("ad-list")
    otis.login(verified_user())
    otis.get_20x("ad-list")


@pytest.mark.django_db
def test_ad_list_only_shows_enabled(otis) -> None:
    one_on_one = AssistantListingFactory.create(
        offers_one_on_one=True, offers_group=False
    )
    unavailable = AssistantListingFactory.create(
        offers_one_on_one=False, offers_group=False
    )
    disabled = AssistantListingFactory.create(
        enabled=False,
        email="disabled@example.com",
        blurb="I am not alive.",
    )
    AssistantFactory.create()
    otis.login(verified_user())

    resp = otis.get_20x("ad-list")
    assert set(resp.context["listings"]) == {one_on_one, unavailable}
    otis.assert_not_has(resp, disabled.assistant.name)
    otis.assert_not_has(resp, "disabled@example.com")
    otis.assert_not_has(resp, "I am not alive.")


@pytest.mark.django_db
def test_ad_list_prompts_for_non_staff(otis) -> None:
    otis.login(verified_user())
    resp = otis.get_20x("ad-list")
    assert resp.context["current_assistant"] is None
    otis.assert_no_testid(resp, "ad-update-prompt")
    otis.assert_no_testid(resp, "ad-enable-prompt")
    otis.assert_no_testid(resp, "ad-not-instructor")


@pytest.mark.django_db
def test_ad_list_prompts_for_staff_without_assistant(otis) -> None:
    otis.login(verified_user(is_staff=True))
    resp = otis.get_20x("ad-list")
    otis.assert_no_testid(resp, "ad-update-prompt")
    otis.assert_no_testid(resp, "ad-enable-prompt")
    otis.assert_testid(resp, "ad-not-instructor")


@pytest.mark.django_db
def test_ad_list_prompts_assistant_without_listing(otis) -> None:
    otis.login(verified_assistant().user)
    otis.assert_testid(otis.get_20x("ad-list"), "ad-enable-prompt")


@pytest.mark.django_db
def test_ad_list_prompts_assistant_with_listing(otis) -> None:
    assistant = verified_assistant()
    AssistantListingFactory.create(assistant=assistant)
    otis.login(assistant.user)
    resp = otis.get_20x("ad-list")
    otis.assert_testid(resp, "ad-update-prompt")
    otis.assert_testid(resp, "ad-updated-at")


@pytest.mark.django_db
def test_ad_list_prompts_assistant_with_disabled_listing(otis) -> None:
    assistant = verified_assistant()
    AssistantListingFactory.create(assistant=assistant, enabled=False)
    otis.login(assistant.user)
    resp = otis.get_20x("ad-list")
    assert list(resp.context["listings"]) == []
    otis.assert_testid(resp, "ad-enable-prompt")


@pytest.mark.django_db
def test_ad_list_edit_link_visibility(otis) -> None:
    assistant = verified_assistant()
    AssistantListingFactory.create(assistant=assistant)

    otis.login(assistant.user)
    otis.assert_testid(otis.get_20x("ad-list"), "ad-edit-link")
    otis.login(verified_user())
    otis.assert_no_testid(otis.get_20x("ad-list"), "ad-edit-link")


@pytest.mark.django_db
def test_ad_update_requires_assistant(otis) -> None:
    otis.get_30x("ad-update")
    otis.login(UserFactory.create())
    otis.get_40x("ad-update")
    otis.login(AssistantFactory.create().user)
    otis.get_20x("ad-update")


@pytest.mark.django_db
def test_ad_update_creates_listing(otis) -> None:
    assistant = verified_assistant()
    otis.login(assistant.user)

    resp = otis.post_20x("ad-update", data=LISTING_DATA, follow=True)
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
    listing = AssistantListing.objects.get(assistant=assistant)
    for field, value in LISTING_DATA.items():
        assert getattr(listing, field) == value, field


@pytest.mark.django_db
def test_ad_update_edits_existing_listing(otis) -> None:
    assistant = verified_assistant()
    listing = AssistantListingFactory.create(assistant=assistant)
    original_updated_at = listing.updated_at
    otis.login(assistant.user)

    otis.post_20x("ad-update", data={**LISTING_DATA, "enabled": False}, follow=True)
    listing.refresh_from_db()
    assert not listing.enabled
    assert listing.updated_at > original_updated_at
    assert listing.created_at < listing.updated_at
    assert AssistantListing.objects.count() == 1


@pytest.mark.django_db
def test_ad_update_edits_only_own_listing(otis) -> None:
    assistant1 = AssistantListingFactory.create().assistant
    assistant2 = AssistantFactory.create()

    otis.login(assistant1.user)
    assert otis.get("ad-update").context["listing"].assistant == assistant1

    otis.login(assistant2.user)
    listing = otis.get("ad-update").context["listing"]
    assert listing.assistant == assistant2
    assert listing.pk is None


@pytest.mark.django_db
def test_listing_links() -> None:
    listing = AssistantListingFactory.create(website="https://example.com/")
    assert [label for _, label, _ in listing.links] == ["website"]
    assert listing.links[0][2] == "https://example.com/"
