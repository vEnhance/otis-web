from django.db.models import Q

def get_visible(user, queryset):
	"""From a queryset, filter out the students which the user can see."""
	# Otherwise, do listing
	if user.is_staff:
		return queryset
	else:
		return queryset.filter(Q(user = user) | Q(assistant__user = user))
