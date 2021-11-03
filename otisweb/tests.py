from typing import Any, Dict, Union

import factory
import factory.random
from django.contrib.auth.models import User
from django.db import models
from django.http.response import HttpResponse
from django.test import TestCase
from django.test.client import Client
from django.urls.base import reverse_lazy

factory.random.reseed_random('otisweb')


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

	def assert20X(self, response: HttpResponse):
		self.assertGreaterEqual(response.status_code, 200)
		self.assertLess(response.status_code, 300)
		return response

	def assertOK(self, response: HttpResponse):
		self.assertLess(response.status_code, 400)
		return response

	def assert40X(self, response: HttpResponse):
		self.assertGreaterEqual(response.status_code, 400)
		self.assertLess(response.status_code, 500)
		return response

	def assertDenied(self, response: HttpResponse):
		self.assertEqual(response.status_code, 403)
		return response

	def assertNotFound(self, response: HttpResponse):
		self.assertEqual(response.status_code, 404)
		return response

	def get(self, name: str, *args: Any):
		return self.client.get(reverse_lazy(name, args=args), follow=True)

	def post(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.client.post(reverse_lazy(name, args=args), data=data, follow=True)

	def assertGet20X(self, name: str, *args: Any):
		return self.assert20X(self.get(name, *args))

	def assertGetOK(self, name: str, *args: Any):
		return self.assertOK(self.get(name, *args))

	def assertGet40X(self, name: str, *args: Any):
		return self.assert40X(self.get(name, *args))

	def assertGetDenied(self, name: str, *args: Any):
		return self.assertDenied(self.get(name, *args))

	def assertGetNotFound(self, name: str, *args: Any):
		return self.assertNotFound(self.get(name, *args))

	def assertPost20X(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.assert20X(self.post(name, *args, data=data))

	def assertPostOK(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.assertOK(self.post(name, *args, data=data))

	def assertPost40X(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.assert40X(self.post(name, *args, data=data))

	def assertPostDenied(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.assertDenied(self.post(name, *args, data=data))

	def assertPostNotFound(self, name: str, *args: Any, data: Dict[str, Any] = {}):
		return self.assertNotFound(self.post(name, *args, data=data))

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
