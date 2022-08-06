import datetime
import logging
import os
from typing import List, TypedDict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils import timezone
from mailchimp3 import MailChimp
from mailchimp3.mailchimpclient import MailChimpError


class AuthHttpRequest(HttpRequest):
	user: User


# ----------------------------------------------

logger = logging.getLogger(__name__)


class MailChimpDatum(TypedDict):
	url: str
	title: str
	summary: str
	timestamp: datetime.datetime


API_KEY = os.getenv('MAILCHIMP_API_KEY')


def get_client() -> MailChimp:
	return MailChimp(mc_api=API_KEY, mc_user='vEnhance')


def get_mailchimp_campaigns(days: int) -> List[MailChimpDatum]:
	if API_KEY is None:
		# TODO would eventually be good to find some way to fake this data for people not named Evan
		logger.warning("Using fake mailchimp data")
		example: MailChimpDatum = {
			'url': 'http://www.example.com',
			'title': 'Example email',
			'summary': 'Why hello there',
			'timestamp': timezone.now()
		}
		return [example]
	else:
		client = get_client()
		timestamp = (timezone.now() - datetime.timedelta(days=days))
		try:
			mailchimp_campaign_data = client.campaigns.all(
				get_all=True, status='sent', since_send_time=timestamp
			)
		except MailChimpError:
			return []
		if mailchimp_campaign_data is not None:
			campaigns = mailchimp_campaign_data['campaigns']
			data: List[MailChimpDatum] = [
				{
					'url': c['archive_url'],
					'title': c['settings']['subject_line'],
					'summary': c['settings']['preview_text'],
					'timestamp': datetime.datetime.fromisoformat(c['send_time'])
				} for c in campaigns
			]
			data.sort(key=lambda datum: datum['timestamp'], reverse=True)
			return data
		else:
			return []


def mailchimp_subscribe(request: AuthHttpRequest):
	user = request.user
	if settings.TESTING or settings.DEBUG:
		logger.warning(f"Not actually subscribing {user} since we're testing")
		return
	elif API_KEY is not None:
		try:
			client = MailChimp(mc_api=API_KEY, mc_user='vEnhance')
			client.lists.members.create(
				os.getenv('MAILCHIMP_LIST_ID'), {
					'email_address': user.email,
					'status': 'subscribed',
					'merge_fields': {
						'FNAME': user.first_name,
						'LNAME': user.last_name,
					}
				}
			)
			messages.success(
				request, f"The email {user.email} is now listed as the " +
				"contact point for OTIS announcements from Evan."
			)
		except MailChimpError as e:
			logger.error(f"Could not add {user.email} to MailChimp", exc_info=e)
			messages.warning(
				request,
				f"The email {user.email} could not be added to MailChimp, maybe it's subscribed already?"
			)
	else:
		raise Exception("No API KEY provided in production!")
