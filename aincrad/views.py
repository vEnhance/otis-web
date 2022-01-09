from hashlib import sha256
from typing import Any, Dict

from allauth.socialaccount.models import SocialAccount
from arch.models import Hint, Problem
from core.models import Unit
from dashboard.models import ProblemSuggestion, PSet
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
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


def venueq_handler(action: str, request: HttpRequest) -> JsonResponse:
	if action == 'grade_problem_set':
		# mark problem set as done
		pset = get_object_or_404(PSet, pk=request.POST['pk'])
		pset.approved = bool(request.POST['approved'])
		pset.clubs = request.POST.get('clubs', None)
		pset.hours = request.POST.get('hours', None)
		pset.save()
		if pset.resubmitted is False:
			# unlock the unit the student asked for
			finished_unit = get_object_or_404(Unit, pk=request.POST['unit__pk'])
			student = get_object_or_404(Student, pk=request.POST['student__pk'])
			if 'next_unit_to_unlock__pk' in request.POST:
				target = get_object_or_404(Unit, pk=request.POST['next_unit_to_unlock__pk'])
				student.unlocked_units.add(target)
			student.unlocked_units.remove(finished_unit)
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
		suggestion = ProblemSuggestion.objects.get(pk=request.POST['pk'])
		suggestion.resolved = True
		suggestion.eligible = bool(request.POST['eligible'])
		suggestion.save()
		return JsonResponse({'result': 'success'}, status=200)
	elif action == 'init':
		inquiries = UnitInquiry.objects.filter(
			status="NEW",
			student__semester__active=True,
			student__legit=True,
		).annotate(
			total_inquiry_count=SubqueryCount('student__unitinquiry'),
			unlock_inquiry_count=SubqueryCount(
				'student__unitinquiry', filter=Q(action_type="UNLOCK")
			),
		)
		data: Dict[str, Any] = {
			'_name':
				'Root',
			'_children':
				[
					{
						'_name':
							'Problem sets',
						'_children':
							list(
								PSet.objects.filter(
									approved=False,
									student__semester__active=True,
									student__legit=True,
								).values(
									'pk',
									'approved',
									'resubmitted',
									'feedback',
									'special_notes',
									'student__pk',
									'student__user__first_name',
									'student__user__last_name',
									'student__user__email',
									'hours',
									'clubs',
									'eligible',
									'unit__group__name',
									'unit__code',
									'unit__pk',
									'next_unit_to_unlock__group__name',
									'next_unit_to_unlock__code',
									'next_unit_to_unlock__pk',
									'upload__content',
								)
							)
					}, {
						'_name':
							'Inquiries',
						'inquiries':
							list(
								inquiries.values(
									'pk',
									'unit__group__name',
									'unit__code',
									'student__user__first_name',
									'student__user__last_name',
									'explanation',
									'created_at',
									'unlock_inquiry_count',
									'total_inquiry_count',
								)
							),
					}, {
						'_name':
							'Suggestions',
						'_children':
							list(
								ProblemSuggestion.objects.filter(resolved=False).values(
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
							)
					}
				],
		}
		return JsonResponse(data, status=200)
	else:
		raise Exception("No such command")


def discord_handler(action: str, request: HttpRequest) -> JsonResponse:
	assert action == 'register'
	# check whether social account exists
	uid = int(request.POST['uid'])
	queryset = SocialAccount.objects.filter(uid=uid)
	if not (n := len(queryset)) == 1:
		return JsonResponse({'result': 'nonexistent', 'length': n})

	social = queryset.get()  # get the social account for this; should never 404
	user = social.user
	student = Student.objects.filter(user=user, semester__active=True).first()
	regform = StudentRegistration.objects.filter(
		user=user, container__semester__active=True
	).first()

	if student is not None:
		return JsonResponse(
			{
				'result': 'success',
				'user': social.user.username,
				'name': social.user.get_full_name(),
				'uid': uid,
				'track': student.track,
				'gender': regform.gender if regform is not None else '?',
				'country': regform.country if regform is not None else '???',
				'num_years': Student.objects.filter(user=user).count(),
			}
		)
	elif student is None and regform is not None:
		return JsonResponse({'result': 'pending'})
	else:
		return JsonResponse({'result': 'unregistered'})


def problems_handler(action: str, request: HttpRequest) -> JsonResponse:
	puid = request.POST['puid'].upper()
	if action == 'get_hints':
		problem, _ = Problem.objects.get_or_create(puid=puid)
		hints = list(
			Hint.objects.filter(problem=problem).values('keywords', 'id', 'number', 'content')
		)
		return JsonResponse({'hints': hints})
	elif action == 'add_hints':
		problem, _ = Problem.objects.get_or_create(puid=puid)
		content = request.POST['content']
		existing_hint_numbers = set(
			Hint.objects.filter(problem=problem).values_list('number', flat=True)
		)
		if 'number' in request.POST:
			number = int(request.POST['number'])
		else:
			number = 0
			while number in existing_hint_numbers:
				number += 10
		keywords = request.POST.get('keywords', "imported from discord")
		hint = Hint.objects.create(
			problem=problem, number=number, content=content, keywords=keywords
		)
		return JsonResponse({'pk': hint.pk, 'number': number})
	else:
		raise NotImplementedError(action)


def invoice_handler(action: str, request: HttpRequest) -> JsonResponse:
	def sanitize(s: str, last: bool = False) -> str:
		return unidecode(s).lower().split(' ', maxsplit=1)[-1 if last else 0]

	invoices = Invoice.objects.filter(student__semester__active=True)
	invoices = invoices.select_related('student__user')
	fields = ('adjustment', 'extras', 'total_paid')
	data = request.POST.dict()
	del data['token']
	del data['action']
	for inv in invoices:
		if inv.student.user is not None:
			first_name = sanitize(inv.student.user.first_name)
			last_name = sanitize(inv.student.user.last_name, last=True)
			for k in fields:
				if (x := data.pop(f'{k}.{first_name}.{last_name}', None)) is not None:
					assert isinstance(x, str)
					setattr(inv, k, float(x))
	Invoice.objects.bulk_update(invoices, fields, batch_size=25)
	return JsonResponse(data)


@csrf_exempt
@require_POST
def api(request: HttpRequest) -> JsonResponse:
	action = request.POST.get('action', None)
	if action is None:
		raise SuspiciousOperation('You need to provide an action, silly')
	if settings.PRODUCTION:
		token = request.POST.get('token')
		assert token is not None
		if not sha256(token.encode('ascii')).hexdigest() == settings.API_TARGET_HASH:
			return JsonResponse({'error': "☕"}, status=418)

	if action in ('grade_problem_set', 'approve_inquiries', 'mark_suggestion', 'init'):
		return venueq_handler(action, request)
	elif action in ('register', ):
		return discord_handler(action, request)
	elif action in ('get_hints', 'add_hints'):
		return problems_handler(action, request)
	elif action in ('invoice', ):
		return invoice_handler(action, request)
	else:
		return JsonResponse({'error': 'No such command'}, status=400)


# vim: fdm=indent
