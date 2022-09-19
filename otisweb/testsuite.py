import json
import logging
import pprint
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Union

import factory
import factory.random
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from django.test.client import Client
from django.urls.base import reverse_lazy

factory.random.reseed_random('otisweb')

# OKAY TIME TO MONKEY PATCH THE MONKEY PATCH
if TYPE_CHECKING:  # pragma: no cover
	from django.test.client import _MonkeyPatchedWSGIResponse  # type: ignore  # NOQA
	MonkeyResponseType = _MonkeyPatchedWSGIResponse
else:
	MonkeyResponseType = Any


# waiting on https://github.com/FactoryBoy/factory_boy/pull/820 ...
class UniqueFaker(factory.Faker):
	# based on factory.faker.Faker.generate
	def generate(self, **params: Any) -> Any:
		locale = params.pop('locale')
		subfaker = self._get_faker(locale)
		return subfaker.unique.format(self.provider, **params)


class OTISTestCase(TestCase):
	def setUp(self):
		self.client = Client()

	def debug_short(self, response: MonkeyResponseType) -> str:
		d: Dict[str, Any] = {}
		for key in ('headers', 'json', 'redirect_chain', 'request', 'wsgi_request'):
			d[key] = getattr(response, key, None)
		return '\n' + pprint.pformat(d, compact=False, depth=3) + '\n'

	def debug_dump(self, response: MonkeyResponseType) -> None:
		timestamp = datetime.utcnow().strftime('%d_%b_%Y_%H%M%S')
		html_path = Path(f"/tmp/{settings.WSGI_APPLICATION}.tests/{timestamp}.html")
		txt_path = Path(f"/tmp/{settings.WSGI_APPLICATION}.tests/{timestamp}.txt")

		try:
			html_path.parent.mkdir(exist_ok=True)
		except PermissionError:
			pass
		else:
			if len(response.content) > 0:
				logging.info(f"Wrote to {html_path}")
				html_path.write_bytes(response.content)
				txt_path.write_text(pprint.pformat(response.__dict__, depth=3))

	def assertHas(
		self, response: MonkeyResponseType, text: Union[bytes, int, str], **kwargs: Any
	):
		try:
			self.assertContains(response, text, **kwargs, msg_prefix=self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertNotHas(self, response: MonkeyResponseType, text: Union[bytes, str], **kwargs: Any):
		try:
			self.assertNotContains(response, text, **kwargs, msg_prefix=self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertResponse20X(self, response: MonkeyResponseType):
		try:
			self.assertGreaterEqual(response.status_code, 200, self.debug_short(response))
			self.assertLess(response.status_code, 300, self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertResponseOK(self, response: MonkeyResponseType):
		try:
			self.assertLess(response.status_code, 400, self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertResponse40X(self, response: MonkeyResponseType):
		try:
			self.assertGreaterEqual(response.status_code, 400, self.debug_short(response))
			self.assertLess(response.status_code, 500, self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertResponseDenied(self, response: MonkeyResponseType):
		try:
			if response.status_code != 400:
				self.assertEqual(response.status_code, 403, self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def assertResponseNotFound(self, response: MonkeyResponseType):
		try:
			self.assertEqual(response.status_code, 404, self.debug_short(response))
		except AssertionError as e:
			self.debug_dump(response)
			raise e
		else:
			return response

	def get(self, name: str, *args: Any, **kwargs: Any):
		if (json_data := kwargs.pop('json', None)) is not None:
			kwargs['content_type'] = 'application/json'
			kwargs['data'] = json.dumps(json_data)
		return self.client.get(reverse_lazy(name, args=args), **kwargs)

	def post(self, name: str, *args: Any, **kwargs: Any):
		if (json_data := kwargs.pop('json', None)) is not None:
			kwargs['content_type'] = 'application/json'
			kwargs['data'] = json.dumps(json_data)
		return self.client.post(reverse_lazy(name, args=args), **kwargs)

	def url(self, name: str, *args: Any):
		return reverse_lazy(name, args=args)

	def assertGet20X(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponse20X(self.get(name, *args, **kwargs))

	def assertGetOK(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseOK(self.get(name, *args, **kwargs))

	def assertGet40X(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponse40X(self.get(name, *args, **kwargs))

	def assertGetDenied(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseDenied(self.get(name, *args, **kwargs))

	def assertGetNotFound(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseNotFound(self.get(name, *args, **kwargs))

	def assertGetRedirects(self, target: str, name: str, *args: Any, **kwargs: Any):
		resp = self.get(name, *args, **kwargs)
		self.assertRedirects(
			resp,
			expected_url=target,
			target_status_code=200,
			msg_prefix=self.debug_short(resp),
		)
		return resp

	def assertPost20X(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponse20X(self.post(name, *args, **kwargs))

	def assertPostOK(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseOK(self.post(name, *args, **kwargs))

	def assertPost40X(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponse40X(self.post(name, *args, **kwargs))

	def assertPostDenied(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseDenied(self.post(name, *args, **kwargs))

	def assertPostNotFound(self, name: str, *args: Any, **kwargs: Any):
		return self.assertResponseNotFound(self.post(name, *args, **kwargs))

	def assertPostRedirects(self, target: str, name: str, *args: Any, **kwargs: Any):
		resp = self.post(name, *args, **kwargs)
		self.assertRedirects(
			resp,
			expected_url=target,
			target_status_code=200,
			msg_prefix=self.debug_short(resp),
		)
		return resp

	def login_name(self, username: str):
		user = User.objects.get(username=username)
		self.client.force_login(user)
		return user

	def login(self, obj: Union[str, models.Model]):
		if isinstance(obj, str):
			return self.login_name(obj)
		elif isinstance(obj, User):
			self.client.force_login(obj)
			return obj
		elif hasattr(obj, 'user'):
			user = getattr(obj, 'user')
			self.client.force_login(user)
			return user

	def assertGetBecomesLoginRedirect(self, name: str, *args: Any):
		redirectURL = '/accounts/login/?next=' + reverse_lazy(name, args=args)
		resp = self.get(name, *args)
		self.assertRedirects(resp, redirectURL)
		return resp

	def assertPostBecomesLoginRedirect(self, name: str, *args: Any, **kwargs: Any):
		redirectURL = '/accounts/login?next=' + reverse_lazy(name, args=args)
		resp = self.post(name, *args, **kwargs)
		self.assertRedirects(resp, redirectURL)
		return resp
