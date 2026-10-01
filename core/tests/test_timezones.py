import datetime
from unittest.mock import Mock, PropertyMock

import pytest
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory

from core.factories import UserFactory, UserProfileFactory
from core.middleware import TimezoneMiddleware
from core.models import UserProfile, validate_timezone


@pytest.mark.django_db
def test_timezone_validator():
    # Valid timezones should not raise
    validate_timezone("")  # blank is allowed
    validate_timezone("America/New_York")
    validate_timezone("Europe/London")
    validate_timezone("Asia/Tokyo")
    validate_timezone("UTC")

    # Invalid timezones should raise ValidationError
    with pytest.raises(ValidationError):
        validate_timezone("Invalid/Timezone")
    with pytest.raises(ValidationError):
        validate_timezone("Not_A_Timezone")


@pytest.mark.django_db
def test_user_profile_timezone():
    user = UserFactory.create()
    profile = UserProfile.objects.create(user=user, timezone="America/Los_Angeles")
    profile.full_clean()  # Should not raise
    assert profile.timezone == "America/Los_Angeles"

    # Test blank timezone is allowed
    profile.timezone = ""
    profile.full_clean()  # Should not raise

    # Test invalid timezone raises validation error
    profile.timezone = "Invalid/Zone"
    with pytest.raises(ValidationError):
        profile.full_clean()


@pytest.mark.django_db
def test_timezone_middleware():
    # Test 1: User with valid timezone
    user1 = UserFactory.create()
    UserProfile.objects.create(user=user1, timezone="America/Los_Angeles")

    request = Mock()
    request.user = user1
    type(request.user).is_authenticated = PropertyMock(return_value=True)

    mock_response = Mock()
    get_response = Mock(return_value=mock_response)
    middleware = TimezoneMiddleware(get_response)

    response = middleware(request)
    assert response == mock_response
    get_response.assert_called_once()

    # Test 2: User with no timezone set (should use default)
    user2 = UserFactory.create()
    UserProfile.objects.create(user=user2, timezone="")

    request2 = Mock()
    request2.user = user2
    type(request2.user).is_authenticated = PropertyMock(return_value=True)

    get_response2 = Mock(return_value=mock_response)
    middleware2 = TimezoneMiddleware(get_response2)

    response2 = middleware2(request2)
    assert response2 == mock_response
    get_response2.assert_called_once()

    # Test 3: Unauthenticated user
    request3 = Mock()
    request3.user = Mock()
    type(request3.user).is_authenticated = PropertyMock(return_value=False)

    get_response3 = Mock(return_value=mock_response)
    middleware3 = TimezoneMiddleware(get_response3)

    response3 = middleware3(request3)
    assert response3 == mock_response
    get_response3.assert_called_once()


@pytest.mark.django_db
def test_timezone_middleware_does_not_create_profile():
    user = UserFactory.create()
    assert not UserProfile.objects.filter(user=user).exists()

    request = RequestFactory().get("/")
    request.user = user

    middleware = TimezoneMiddleware(lambda _: HttpResponse("ok"))
    middleware(request)

    assert not UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_timezone_in_profile_form(otis):
    user = UserFactory.create()
    otis.login(user)

    # Get the profile preferences page
    response = otis.get("profile")

    # Verify timezone field is in the form
    content = response.content.decode()
    assert "timezone" in content.lower() or "time zone" in content.lower()
    assert "id_timezone" in content
    assert '<select name="timezone"' in content
    assert "Asia/Seoul" in content

    # Verify we can set and save timezone directly on model
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.timezone = "Europe/Paris"
    profile.save()

    profile.refresh_from_db()
    assert profile.timezone == "Europe/Paris"


@pytest.mark.django_db
def test_profile_timezone_choices_order(otis):
    user = UserFactory.create()
    otis.login(user)

    response = otis.get_20x("profile")
    timezone_choices = response.context["timezone_choices"]

    assert timezone_choices[:7] == [
        "Pacific/Honolulu",
        "America/Anchorage",
        "America/Los_Angeles",
        "America/Phoenix",
        "America/Denver",
        "America/Chicago",
        "America/New_York",
    ]
    assert "Europe/London" in timezone_choices


@pytest.mark.django_db
def test_profile_timezone_search_js(otis):
    user = UserFactory.create()
    otis.login(user)

    response = otis.get_20x("profile")
    content = response.content.decode()

    # JS uses longGeneric for search (e.g. "Pacific Time") and shortOffset for display
    assert "timeZoneName: 'longGeneric'" in content
    assert "timeZoneName: 'shortOffset'" in content
    # Underscore normalization comment should be present
    assert "Los_Angeles" in content
    assert "Asia/Seoul" in content
    assert "Europe/Vienna" in content


@pytest.mark.django_db
def test_timestamps_use_the_viewers_timezone(otis):
    target = UserFactory.create(
        date_joined=datetime.datetime(2026, 9, 12, 23, 30, tzinfo=datetime.UTC)
    )
    admin = UserFactory.create(is_superuser=True, is_staff=True)
    UserProfileFactory.create(user=admin, timezone="Asia/Manila")
    otis.login(admin)

    resp = otis.get_ok("user-info", target.pk)
    otis.assert_has(resp, "2026-09-13 07:30 PST")
