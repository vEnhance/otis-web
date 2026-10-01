from django.contrib.auth.models import Group, User

from core.factories import UserFactory
from tubes.factories import OIMEContributorFactory
from tubes.models import OIMEContributor


def verified_contributor(username: str = "alice") -> tuple[User, OIMEContributor]:
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(username=username, groups=(verified_group,))
    return user, OIMEContributorFactory.create(user=user)


def verified_staff(username: str = "staff") -> tuple[User, OIMEContributor]:
    verified_group, _ = Group.objects.get_or_create(name="Verified")
    user = UserFactory.create(
        username=username, is_staff=True, groups=(verified_group,)
    )
    return user, OIMEContributorFactory.create(user=user)
