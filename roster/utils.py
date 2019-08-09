from django.db.models import Q
from django.http import Http404

def get_visible(user, queryset):
	"""From a queryset, filter out the students which the user can see."""
	# Otherwise, do listing
	if user.is_staff:
		return queryset
	else:
		return queryset.filter(Q(user = user) | Q(assistant__user = user))

def check_can_view(request, student):
	if not student.can_view_by(request.user):
		raise Http404("%s cannot view %s" %(request.user, student))
def check_taught_by(request, student):
	if not student.is_taught_by(request.user):
		raise Http404("%s cannot edit %s" %(request.user, student))
