from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied  # NOQA
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden  # NOQA
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from roster.models import Invoice, Student
from .models import PaymentLog
import logging
import stripe


def invoice(request: HttpRequest, student_id: int, checksum: str) -> HttpResponse:
	student = get_object_or_404(Student, id=student_id)

	if checksum != student.get_checksum(settings.INVOICE_HASH_KEY):
		raise PermissionDenied("Bad hash provided")
	try:
		invoice = student.invoice
	except ObjectDoesNotExist:
		raise Http404("No invoice exists for this student")
	context = {
		'title': "Payment for " + student.name,
		'student': student,
		'invoice': invoice,
		'checksum': checksum
	}
	return render(request, "payments/invoice.html", context)


@csrf_exempt
def config(request: HttpRequest) -> HttpResponse:
	if request.method == 'GET':
		stripe_config = {'publicKey': settings.STRIPE_PUBLISHABLE_KEY}
		return JsonResponse(stripe_config, safe=False)
	else:
		return HttpResponseForbidden('Need to use request method GET')


@csrf_exempt
def checkout(request: HttpRequest, amount: int, invoice_id: int) -> HttpResponse:
	if amount <= 0:
		raise PermissionDenied("Need to enter a positive amount for payment...")
	stripe.api_key = settings.STRIPE_SECRET_KEY
	if settings.PRODUCTION:
		domain_url = 'https://otis.evanchen.cc'
	else:
		domain_url = 'http://127.0.0.1:8000'
	if request.method == 'GET':
		checkout_session = stripe.checkout.Session.create(
			client_reference_id=invoice_id,
			success_url=domain_url + '/payments/success/',
			cancel_url=domain_url + '/payments/cancelled/',
			payment_method_types=['card'],
			mode='payment',
			line_items=[
				{
					'name': 'OTIS Payment',
					'quantity': 1,
					'currency': 'usd',
					'amount': amount * 100,
				}
			]
		)
		return JsonResponse({'sessionId': checkout_session['id']})
	else:
		return HttpResponseForbidden('Need to use request method GET')


@csrf_exempt
def webhook(request: HttpRequest) -> HttpResponse:
	if request.method != 'POST':
		return HttpResponseForbidden("Need to use request method POST")
	stripe.api_key = settings.STRIPE_SECRET_KEY
	endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
	payload = request.body
	sig_header = request.META['HTTP_STRIPE_SIGNATURE']

	try:
		event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
	except ValueError as e:
		# Invalid payload
		logging.error(e)
		return HttpResponse(status=400)
	except stripe.error.SignatureVerificationError as e:  # type: ignore
		# Invalid signature
		logging.error(e)
		return HttpResponse(status=400)

	# Handle the checkout.session.completed event
	if event['type'] == 'checkout.session.completed':
		logging.debug("Payment was successful.")
		logging.debug(event)
		invoice_id = int(event['data']['object']['client_reference_id'])
		amount = int(event['data']['object']['amount_total'] / 100)
		invoice = get_object_or_404(Invoice, id=invoice_id)
		invoice.total_paid += amount
		invoice.save()
		payment_log = PaymentLog(amount=amount, invoice=invoice)
		payment_log.save()
	return HttpResponse(status=200)


def success(request: HttpRequest) -> HttpResponse:
	return render(request, "payments/success.html")


def cancelled(request: HttpRequest) -> HttpResponse:
	return HttpResponse("Cancelled payment")
