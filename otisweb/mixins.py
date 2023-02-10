from braces.views import GroupRequiredMixin


class VerifiedRequiredMixin(GroupRequiredMixin):
    group_required = "Verified"
    raise_exception = False
