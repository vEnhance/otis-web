from typing import Any

from django.contrib.auth.models import User
from django.http.response import HttpResponse
from django.test import TestCase
from django.test.client import Client
from django.urls.base import reverse_lazy


class OTISTestCase(TestCase):
	fixtures = ('testdata.yaml', )

	def setUp(self):
		self.client = Client()

	def assert20X(self, response: HttpResponse):
		self.assertGreaterEqual(response.status_code, 200)
		self.assertLess(response.status_code, 300)

	def assertOK(self, response: HttpResponse):
		self.assertLess(response.status_code, 400)

	def assert40X(self, response: HttpResponse):
		self.assertGreaterEqual(response.status_code, 400)
		self.assertLess(response.status_code, 500)

	def assertDenied(self, response: HttpResponse):
		self.assertEqual(response.status_code, 403)

	def get(self, name: str, *args: Any):
		return self.client.get(reverse_lazy(name, args=args))

	def post(self, name: str, *args: Any, **kwargs: Any):
		return self.client.post(reverse_lazy(name, args=args), kwargs)

	def assertGet20X(self, name: str, *args: Any):
		self.assert20X(self.get(name, *args))

	def assertGetOK(self, name: str, *args: Any):
		self.assertOK(self.get(name, *args))

	def assertGet40X(self, name: str, *args: Any):
		self.assert40X(self.get(name, *args))

	def assertGetDenied(self, name: str, *args: Any):
		self.assertDenied(self.get(name, *args))

	def assertPost20X(self, name: str, *args: Any, **kwargs: Any):
		self.assert20X(self.post(name, *args, **kwargs))

	def assertPostOK(self, name: str, *args: Any, **kwargs: Any):
		self.assertOK(self.post(name, *args, **kwargs))

	def assertPost40X(self, name: str, *args: Any, **kwargs: Any):
		self.assert40X(self.post(name, *args, **kwargs))

	def assertPostDenied(self, name: str, *args: Any, **kwargs: Any):
		self.assertDenied(self.post(name, *args, **kwargs))

	def login(self, username: str):
		self.client.force_login(User.objects.get(username=username))

	def assertGetBecomesLoginRedirect(self, name: str, *args: Any):
		self.assertRedirects(
			self.get(name, *args), '/accounts/login/?next=' + reverse_lazy(name, args=args)
		)

	def assertPostBecomesLoginRedirect(self, name: str, *args: Any, **kwargs: Any):
		redirectURL = '/accounts/login?next=' + reverse_lazy(name, args=args)
		self.assertRedirects(self.post(name, *args, **kwargs), redirectURL)
