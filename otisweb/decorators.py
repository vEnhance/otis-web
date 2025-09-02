from collections.abc import Awaitable
from typing import Callable, TypeVar

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http.response import HttpResponseBase

AnyUser = AbstractBaseUser | AnonymousUser

_VIEW = TypeVar(
    "_VIEW", bound=Callable[..., HttpResponseBase | Awaitable[HttpResponseBase]]
)


def auth_test(
    func: Callable[[User], bool],
    error_msg: str | None = None,
) -> Callable[[AnyUser], bool]:
    def ret(user: AnyUser):
        if not isinstance(user, User):
            return False
        if func(user) is True:
            return True
        else:
            raise PermissionDenied(error_msg)

    return ret


def verified_required(view_func: _VIEW) -> _VIEW:
    """
    Decorator for views that checks that the user is logged in and is in Verified group.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.groups.filter(name="Verified").exists() or u.is_staff,
            error_msg="Not in Verified group",
        ),
    )
    return actual_decorator(view_func)


def staff_required(view_func: _VIEW) -> _VIEW:
    """
    Decorator for views that checks that the user is logged in and is staff.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.is_staff,
            error_msg="Not a staff member",
        ),
    )
    return actual_decorator(view_func)


def admin_required(view_func: _VIEW) -> _VIEW:
    """
    Decorator for views that checks that the user is logged in and is an admin.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.is_staff and u.is_superuser,
            error_msg="Not an administrator",
        ),
    )
    return actual_decorator(view_func)
