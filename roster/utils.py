def get_visible(user, queryset):
	"""From a queryset, filter out the students which the user can see."""
	# Otherwise, do listing
	if user.is_staff:
		students = queryset
	else:
		students = queryset.filter(Q(user = request.user) | Q(assistant__user = request.user))
