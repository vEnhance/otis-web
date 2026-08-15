"""Custom django-allauth adapters for OTIS-WEB."""

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

# Value of allauth's ``process`` parameter meaning "sign in to an account that
# already exists, and refuse to silently create a new one instead".
#
# Vanilla allauth only distinguishes "connect" and "redirect" from everything
# else, so an unrecognized value like this one behaves exactly like the usual
# "login" process. It is stashed in the social login state before the redirect
# to the provider and read back out of ``sociallogin.state`` on the callback,
# which is where ``OTISSocialAccountAdapter.pre_social_login`` intercepts it.
# Templates hardcode this string; ``otisweb.tests`` checks they agree with it.
AUTH_PROCESS_LOGIN_EXISTING = "login_existing"


def _provider_names(request: HttpRequest) -> dict[str, str]:
    """Map each configured provider's id onto its human-readable name."""
    return {
        provider.sub_id: provider.name
        for provider in get_socialaccount_adapter().list_providers(request)
    }


def _get_verified_emails(sociallogin: SocialLogin) -> set[str]:
    """Return the email addresses the provider vouched for, lowercased.

    Only verified addresses are used: an unverified one proves nothing about
    who is sitting at the keyboard, so it must not be used to reveal anything
    about the accounts we already have.
    """
    return {
        email_address.email.lower()
        for email_address in sociallogin.email_addresses
        if email_address.verified and email_address.email
    }


def _get_login_hint(request: HttpRequest, sociallogin: SocialLogin) -> str:
    """Describe how the owner of these emails signed up, if we can tell.

    This is the whole point of the exercise: the people who end up with
    duplicate accounts are the ones who forgot which button they clicked
    last year, so tell them.
    """
    emails = _get_verified_emails(sociallogin)
    if not emails:
        return ""
    owns_email = Q(user__email__in=emails) | Q(user__emailaddress__email__in=emails)
    provider_ids = {
        str(provider_id)
        for provider_id in SocialAccount.objects.filter(owns_email).values_list(
            "provider", flat=True
        )
        if provider_id
    }
    if provider_ids:
        names = _provider_names(request)
        listed = ", ".join(sorted(names.get(pk, pk) for pk in provider_ids))
        return (
            "By the way, there is already an OTIS account with that email address "
            f"which signs in with: {listed}."
        )
    if (
        User.objects.filter(email__in=emails).exists()
        or EmailAddress.objects.filter(email__in=emails).exists()
    ):
        return (
            "By the way, there is already an OTIS account with that email address, "
            "but it has no social connections attached, "
            "so you probably signed up with a username and password."
        )
    return ""


class OTISSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that can refuse to create an account during a social login."""

    def get_no_existing_account_message(
        self, request: HttpRequest, sociallogin: SocialLogin
    ) -> str:
        provider = getattr(sociallogin, "provider", None)
        provider_name = provider.name if provider is not None else "that provider"
        message = (
            f"You asked to log in with an existing {provider_name} connection, "
            f"but no OTIS account is linked to that {provider_name} account, "
            "so no new account was created. "
            "If you already have an OTIS account, log in the way you did before "
            "and then use the 🔐 icon in the sidebar to attach "
            f"{provider_name} to it. "
            "If you are a newly accepted student who needs a brand new account, "
            "use the section about being accepted to OTIS for the first time."
        )
        hint = _get_login_hint(request, sociallogin)
        return f"{message} {hint}".strip()

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        super().pre_social_login(request, sociallogin)
        if sociallogin.state.get("process") != AUTH_PROCESS_LOGIN_EXISTING:
            return
        if sociallogin.is_existing:
            return
        messages.error(
            request, self.get_no_existing_account_message(request, sociallogin)
        )
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse("account_login")))
