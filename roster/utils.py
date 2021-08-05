from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from . import models


def get_current_students(queryset = models.Student.objects):
	return queryset.filter(semester__active=True)

def get_visible_from_queryset(user, queryset):
	"""From a queryset, filter out the students which the user can see."""
	if user.is_staff:
		return queryset
	else:
		return queryset.filter(Q(user = user) | Q(assistant__user = user)
				| Q(unlisted_assistants__user = user))

def get_visible_students(user, current = True):
	if current:
		queryset = get_current_students()
	else:
		queryset = models.Student.objects.all()
	return get_visible_from_queryset(user, queryset)

def check_can_view(request, student, delinquent_check = True):
	if not student.can_view_by(request.user):
		raise PermissionDenied(f"{request.user} cannot view this student")
	if delinquent_check is True and is_delinquent_locked(request, student):
		raise PermissionDenied("Missing payment permission error")

def is_delinquent_locked(request, student):
	return not request.user.is_staff \
			and student.is_payment_locked \
			and student.invoice.forgive is False
			# student.invoice must exist if student.is_payment_locked is True

def check_taught_by(request, student):
	if not student.is_taught_by(request.user):
		raise PermissionDenied(f"{request.user} cannot edit this student")

def get_student(student_id):
	return get_object_or_404(models.Student.objects, id=student_id)

def infer_student(request):
	return get_object_or_404(models.Student.objects,
				semester__active = True, user = request.user)
