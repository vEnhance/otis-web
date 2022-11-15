from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User


def admin_required( # type: ignore
	view_func = None, # type: ignore
	redirect_field_name=REDIRECT_FIELD_NAME,
	login_url="admin:login",
):
	"""
    Decorator for views that checks that the user is logged in and is a staff
    member, redirecting to the login page if necessary.
    """
	actual_decorator = user_passes_test(
		lambda u: isinstance(u, User) and u.is_active and u.is_staff and u.is_superuser,
		login_url=login_url,
		redirect_field_name=redirect_field_name,
	)
	if view_func:
		return actual_decorator(view_func)
	return actual_decorator
