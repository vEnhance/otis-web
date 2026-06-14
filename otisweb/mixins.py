from typing import Any

from braces.views import (
    GroupRequiredMixin,
    StaffuserRequiredMixin,
    SuperuserRequiredMixin,
)


class StaffRequiredMixin(StaffuserRequiredMixin):
    raise_exception = True
    redirect_unauthenticated_users = True


class AdminRequiredMixin(SuperuserRequiredMixin):
    raise_exception = True
    redirect_unauthenticated_users = True


class VerifiedRequiredMixin(GroupRequiredMixin):
    group_required = "Verified"
    raise_exception = True
    redirect_unauthenticated_users = True

    def check_membership(self, groups: Any) -> bool:
        return self.request.user.is_staff or super().check_membership(groups)  # type: ignore[union-attr]
