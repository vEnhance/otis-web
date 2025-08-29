from typing import Callable

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
from django.core.exceptions import PermissionDenied

AnyUser = AbstractBaseUser | AnonymousUser


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


def verified_required(  # type: ignore
    view_func=None,  # type: ignore
    redirect_field_name=REDIRECT_FIELD_NAME,
    login_url: str | None = None,
):
    """
    Decorator for views that checks that the user is logged in and is in Verified group.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.groups.filter(name="Verified").exists() or u.is_staff,
            error_msg="Not in Verified group",
        ),
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )
    return actual_decorator(view_func) if view_func else actual_decorator


def staff_required(  # type: ignore
    view_func=None,  # type: ignore
    redirect_field_name=REDIRECT_FIELD_NAME,
    login_url="admin:login",
):
    """
    Decorator for views that checks that the user is logged in and is staff.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.is_staff,
            error_msg="Not a staff member",
        ),
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )
    return actual_decorator(view_func) if view_func else actual_decorator


def admin_required(  # type: ignore
    view_func=None,  # type: ignore
    redirect_field_name=REDIRECT_FIELD_NAME,
    login_url="admin:login",
):
    """
    Decorator for views that checks that the user is logged in and is an admin.
    Redirects anonymous users; 403 error otherwise.
    """
    actual_decorator = user_passes_test(
        auth_test(
            lambda u: u.is_staff and u.is_superuser,
            error_msg="Not an administrator",
        ),
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )
    return actual_decorator(view_func) if view_func else actual_decorator
