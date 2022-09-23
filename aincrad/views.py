import json
from hashlib import sha256
from typing import Any, Dict, List, TypedDict

from allauth.socialaccount.models import SocialAccount
from arch.models import Hint, Problem
from dashboard.models import ProblemSuggestion, PSet
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db.models.aggregates import Sum
from django.db.models.query import prefetch_related_objects
from django.db.models.query_utils import Q
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from roster.models import Invoice, Student, StudentRegistration, UnitInquiry
from sql_util.aggregates import SubqueryCount
from unidecode import unidecode

# Create your views here.


class HintData(TypedDict):
	content: str
	number: int
	keywords: str


class JSONData(TypedDict):
	action: str
	token: str

	puid: str
	uid: int
	pk: int
	approved: bool
	rejected: bool
	eligible: bool
	clubs: int
	hours: float

	# keys for add single hint
	content: str
	number: int
	keywords: str

	# keys for add multiple hints
	hints: List[HintData]

	entries: Dict[str, float]


PSET_VENUEQ_INIT_QUERYSET = PSet.objects.filter(
	approved=False,
	rejected=False,
	student__semester__active=True,
	student__legit=True,
	student__enabled=True,
).annotate(
	num_approved_all=SubqueryCount(
		'student__user__student__pset',
		filter=Q(approved=True),
	),
	num_approved_current=SubqueryCount(
		'student__pset',
		filter=Q(approved=True),
	),
).values(
	'pk',
	'approved',
	'rejected',
	'resubmitted',
	'feedback',
	'special_notes',
	'student__user__first_name',
	'student__user__last_name',
	'student__user__email',
	'hours',
	'clubs',
	'unit__group__name',
	'unit__group__slug',
	'unit__code',
	'next_unit_to_unlock__group__name',
	'next_unit_to_unlock__code',
	'upload__content',
	'num_approved_all',
	'num_approved_current',
	'student__reg__country',
	'student__reg__gender',
	'student__reg__graduation_year',
	'student__reg__aops_username',
)

INQUIRY_VENUEQ_INIT_QUERYSET = UnitInquiry.objects.filter(
	status="NEW",
	student__semester__active=True,
	student__legit=True,
).annotate(
	total_inquiry_count=SubqueryCount('student__unitinquiry'),
	unlock_inquiry_count=SubqueryCount('student__unitinquiry', filter=Q(action_type="UNLOCK")),
).values(
	'pk',
	'action_type',
	'unit__group__name',
	'unit__code',
	'student__user__first_name',
	'student__user__last_name',
	'student__user__email',
	'explanation',
	'created_at',
	'unlock_inquiry_count',
	'total_inquiry_count',
	'student__reg__country',
	'student__reg__gender',
	'student__reg__graduation_year',
	'student__reg__aops_username',
)

SUGGESTION_VENUEQ_INIT_QUERYSET = ProblemSuggestion.objects.filter(resolved=False).values(
	'pk',
	'eligible',
	'created_at',
	'user__first_name',
	'user__last_name',
	'user__email',
	'source',
	'description',
	'statement',
	'solution',
	'comments',
	'acknowledge',
	'weight',
	'unit__group__name',
	'unit__code',
)


def venueq_handler(action: str, data: JSONData) -> JsonResponse:
	if action == 'grade_problem_set':
		# mark problem set as done
		pset = get_object_or_404(PSet, pk=data['pk'])
		pset.approved = data['approved']
		pset.rejected = data['rejected']
		pset.clubs = data.get('clubs', None)
		pset.hours = data.get('hours', None)
		pset.save()
		if pset.approved is True and pset.resubmitted is False and pset.unit is not None:
			# unlock the unit the student asked for
			if pset.next_unit_to_unlock is not None:
				pset.student.unlocked_units.add(pset.next_unit_to_unlock)
			# remove the old unit since it's done now
			pset.student.unlocked_units.remove(pset.unit)
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'approve_inquiries':
		for inquiry in UnitInquiry.objects.filter(
			status="NEW",
			student__semester__active=True,
			student__legit=True,
		):
			inquiry.run_accept()
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'mark_suggestion':
		suggestion = get_object_or_404(ProblemSuggestion, pk=data['pk'])
		suggestion.resolved = True
		suggestion.eligible = data['eligible']
		suggestion.save()
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'init':
		output_data: Dict[str, Any] = {}
		output_data['_name'] = 'Root'
		output_data['_children'] = [
			{
				'_name': 'Problem sets',
				'_children': list(PSET_VENUEQ_INIT_QUERYSET)
			}, {
				'_name': 'Inquiries',
				'inquiries': list(INQUIRY_VENUEQ_INIT_QUERYSET)
			}, {
				'_name': 'Suggestions',
				'_children': list(SUGGESTION_VENUEQ_INIT_QUERYSET)
			}
		]
		return JsonResponse(output_data, status=200)
	else:
		raise Exception("No such command")


def discord_handler(action: str, data: JSONData) -> JsonResponse:
	assert action == 'register'
	# check whether social account exists
	uid = data['uid']
	queryset = SocialAccount.objects.filter(uid=uid)
	if not (n := len(queryset)) == 1:
		return JsonResponse({'result': 'nonexistent', 'length': n})

	social = queryset.get()  # get the social account for this; should never 404
	user = social.user
	student = Student.objects.filter(user=user, semester__active=True).first()
	if student is None:
		student = Student.objects.filter(user=user).order_by('-pk').first()
		active = False
	else:
		active = True
	regform = StudentRegistration.objects.filter(user=user).order_by('-pk').first()

	if student is not None:
		return JsonResponse(
			{
				'result': 'success',
				'user': social.user.username,
				'name': student.name,
				'uid': uid,
				'track': student.track,
				'gender': regform.gender if regform is not None else '?',
				'country': regform.country if regform is not None else '???',
				'num_years': Student.objects.filter(user=user).count(),
				'active': active,
			}
		)
	elif student is None and regform is not None:
		return JsonResponse({'result': 'pending'})
	else:
		return JsonResponse({'result': 'unregistered'})


def problems_handler(action: str, data: JSONData) -> JsonResponse:
	if action not in (
		'get_hints',
		'add_hints',
		'add_many_hints',
	):
		raise SuspiciousOperation('Invalid command')
	puid = data['puid'].upper()
	problem, _ = Problem.objects.get_or_create(puid=puid)

	if action == 'get_hints':
		hints = Hint.objects.filter(problem=problem)
		hint_values = hints.values('keywords', 'id', 'number', 'content')
		return JsonResponse({'hints': list(hint_values)})
	elif action == 'add_hints':
		hints = Hint.objects.filter(problem=problem)
		existing_hint_numbers = hints.values_list('number', flat=True)
		if 'number' in data:
			number = data['number']
		else:
			number = 0
			while number in existing_hint_numbers:
				number += 10
		hint = Hint.objects.create(
			problem=problem,
			number=number,
			content=data['content'],
			keywords=data.get('keywords', "imported from discord"),
		)
		return JsonResponse({'pk': hint.pk, 'number': number})
	elif action == 'add_many_hints':
		created_hints = Hint.objects.bulk_create(Hint(problem=problem, **d) for d in data['hints'])
		return JsonResponse({'pks': [h.pk for h in created_hints]})
	else:
		raise NotImplementedError(action)


def invoice_handler(action: str, data: JSONData) -> JsonResponse:
	def sanitize(s: str, last: bool = False) -> str:
		return unidecode(s).lower().split(' ')[-1 if last else 0]

	invoices = Invoice.objects.filter(student__semester__active=True)
	invoices = invoices.select_related('student__user')
	fields = ('adjustment', 'extras', 'total_paid')
	entries = data['entries']
	invoices_to_update: List[Invoice] = []

	for inv in invoices:
		if inv.student.user is not None:
			first_name = sanitize(inv.student.user.first_name)
			last_name = sanitize(inv.student.user.last_name, last=True)

			for k in fields:
				if (x := entries.pop(f'{k}.{first_name}.{last_name}', None)) is not None:
					setattr(inv, k, float(x))

					if inv not in invoices_to_update:
						invoices_to_update.append(inv)
	prefetch_related_objects(invoices_to_update, 'paymentlog_set')
	for inv in invoices_to_update:
		stripe_paid = inv.paymentlog_set.aggregate(s=Sum('amount'))['s']  # type: ignore
		stripe_paid = stripe_paid or 0
		inv.total_paid += stripe_paid

	Invoice.objects.bulk_update(invoices_to_update, fields, batch_size=25)
	return JsonResponse(entries)


@csrf_exempt
@require_POST
def api(request: HttpRequest) -> JsonResponse:
	try:
		data = json.loads(request.body)
	except json.decoder.JSONDecodeError:
		raise SuspiciousOperation('Not valid JSON')
	if type(data) != type(JSONData()):  # type: ignore
		raise SuspiciousOperation('Not valid JSON (needs a dict)')

	action = data.get('action', None)
	if action is None:
		raise SuspiciousOperation('You need to provide an action, silly')
	if settings.PRODUCTION:
		token = data.get('token')
		assert token is not None
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error': "☕"}, status=418)

	if action in ('grade_problem_set', 'approve_inquiries', 'mark_suggestion', 'init'):
		return venueq_handler(action, data)
	elif action in ('register', ):
		return discord_handler(action, data)
	elif action in ('get_hints', 'add_hints', 'add_many_hints'):
		return problems_handler(action, data)
	elif action in ('invoice', ):
		return invoice_handler(action, data)
	else:
		return JsonResponse({'error': 'No such command'}, status=400)


# vim: fdm=indent
