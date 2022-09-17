from core.factories import UnitFactory, UserFactory
from otisweb.tests import OTISTestCase

from .factories import URLPathFactory
from .views import WIKI_SUBJECT_CHART, edit_redirect, view_redirect, wiki_redirect  # NOQA


class WikiTest(OTISTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = UserFactory.create(is_staff=True, is_superuser=True)
		root_url = URLPathFactory.create(article__owner=cls.user)
		units_url = URLPathFactory.create(article__owner=cls.user, parent=root_url, slug='units')

		for subject in set(WIKI_SUBJECT_CHART.values()):
			URLPathFactory.create(
				article__owner=cls.user,
				parent=units_url,
				slug=f"list-of-{subject}-units",
			)

	def test_unitgroup_views(self):
		self.login(WikiTest.user)
		for subject, slug in WIKI_SUBJECT_CHART.items():
			unit = UnitFactory.create(group__subject=subject)
			resp = self.assertGet20X('wiki-unitgroup', unit.pk)
			self.assertContains(resp, f"list-of-{slug}-units")

	def test_raw_views(self):
		urlpath = URLPathFactory.create(article__owner=WikiTest.user)
		edit_redirect(urlpath)
		view_redirect(urlpath)
		wiki_redirect(urlpath)
