import pytest
from django.contrib.auth.models import Group

from core.factories import UserFactory
from tubes.factories import (
    OIMEProposalFactory,
)
from tubes.models import OIMEContributor

from .helpers import verified_contributor

# ---------------------------------------------------------------------------
# Verified-gating: no contributor → redirect to setup
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unverified_cannot_access_proposal_list(otis):
    # Unverified → no contributor → redirected to setup → setup enforces @verified_required
    UserFactory.create(username="mallory")
    otis.login("mallory")
    resp = otis.get("oime-proposal-list")
    otis.assert_30x(resp)
    assert resp.url.endswith("/tubes/setup/")
    otis.get_40x("oime-setup")


@pytest.mark.django_db
def test_unverified_cannot_view_proposal_detail(otis):
    proposal = OIMEProposalFactory.create()
    UserFactory.create(username="mallory")
    otis.login("mallory")
    otis.get_40x("oime-proposal-detail", proposal.pk)


@pytest.mark.django_db
def test_no_contributor_redirects_to_setup(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.get("oime-proposal-list")
    otis.assert_30x(resp)
    assert resp.url.endswith("/tubes/setup/")


@pytest.mark.django_db
def test_verified_can_access_setup(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    otis.get_20x("oime-setup")


@pytest.mark.django_db
def test_verified_with_contributor_can_list(otis):
    user, _ = verified_contributor()
    otis.login(user)
    otis.get_20x("oime-proposal-list")


@pytest.mark.django_db
def test_verified_with_contributor_can_view_proposal(otis):
    user, _ = verified_contributor()
    proposal = OIMEProposalFactory.create()
    otis.login(user)
    # A fresh ranked solver is routed from detail to the pre-fight start screen.
    resp = otis.get("oime-proposal-detail", proposal.pk)
    otis.assert_30x(resp)
    assert resp.url.endswith(f"/tubes/proposal/{proposal.pk}/begin/")
    otis.get_20x("oime-start-fight", proposal.pk)


# ---------------------------------------------------------------------------
# Setup / onboarding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_creates_contributor(otis):
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login("alice")
    resp = otis.post("oime-setup", data={"display_name": "Alice A."})
    otis.assert_30x(resp)
    assert OIMEContributor.objects.filter(user=user, display_name="Alice A.").exists()


@pytest.mark.django_db
def test_setup_can_edit_display_name(otis):
    user, contributor = verified_contributor()
    otis.login(user)
    otis.post("oime-setup", data={"display_name": "New Name"})
    contributor.refresh_from_db()
    assert contributor.display_name == "New Name"
