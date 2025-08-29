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
