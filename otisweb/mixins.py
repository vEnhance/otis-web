from braces.views import (
    GroupRequiredMixin,
    StaffuserRequiredMixin,
    SuperuserRequiredMixin,
)
from django.core.exceptions import PermissionDenied


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


class HintsAllowedMixin:    
    def dispatch(self, request, *args, **kwargs):
        if hasattr(request.user, 'profile') and getattr(request.user.profile, 'no_hint_mode', False):
            raise PermissionDenied("Hints are disabled for this user")
        return super().dispatch(request, *args, **kwargs)
