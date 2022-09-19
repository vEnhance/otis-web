from core.factories import UnitFactory, UserFactory
from dashboard.factories import AchievementFactory
from otisweb.testsuite import OTISTestCase

from wikihaxx.mdx.otis import OTISPreprocessor

from .factories import URLPathFactory
from .views import WIKI_SUBJECT_CHART, edit_redirect, view_redirect, wiki_redirect  # NOQA

wiki_sample_bbcode = r"""Hello!

Alice says, "you are a doofus".

Bob says, "no you".

Compute the total number of words exchanged.

(For students: the following two codes are for testing. They are not real diamonds.)

[diamond 000000000000000000000000][/diamond]

[diamond 000000000000000000007E57][/diamond]

[diamond 100000000000000000007E57][/diamond]

[generic]
Name | Evan
Sex | M
Nationality | Taiwan
Known for | EGMO, Napkin, OTIS
Github | vEnhance
Instagram | @evanchen.cc
Twitch | vEnhance
YouTube | vEnhance
[/generic]

[unit nonexistent]
[/unit]

[unit example]
[/unit]
"""


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
			resp = self.assertGet20X('wiki-unitgroup', unit.pk, follow=True)
			self.assertHas(resp, f"list-of-{slug}-units")

	def test_raw_views(self):
		urlpath = URLPathFactory.create(article__owner=WikiTest.user)
		edit_redirect(urlpath)
		view_redirect(urlpath)
		wiki_redirect(urlpath)

	def test_preprocessor(self):
		UnitFactory.create(
			group__name="Example Unit",
			group__slug='example',
			group__subject='M',
			code='DMW',
		)
		AchievementFactory.create(
			code='000000000000000000007E57',
			name="Test Diamond",
			description='Hi.',
		)
		AchievementFactory.create(
			code='100000000000000000007E57',
			name="Test Diamond with no Image",
			description='This is to appease coverage branch',
			image=None
		)

		p = OTISPreprocessor()
		reply = p.run(wiki_sample_bbcode.splitlines())
		self.assertIn(r'Alice says, "you are a doofus".', reply)
		self.assertIn(r'Bob says, "no you".', reply)
		self.assertIn(r'<tr class="danger"><th>Code</th><td>INVALID</td></tr>', reply)
		self.assertIn(r'<tr><th>Name</th><td>Test Diamond</td></tr>', reply)
		self.assertIn(r'<tr><th>Description</th><td>Hi.</td></tr>', reply)
		self.assertIn(r'<td>@evanchen.cc</td>', reply)
		self.assertIn(r'<tr class="danger"><th>Name</th><td>nonexistent</td></tr>', reply)
		self.assertIn(r'<tr><th>Name</th><td>Example Unit</td></tr>', reply)
		self.assertIn(r'<tr><th>Classification</th><td>Miscellaneous</td></tr>', reply)
		self.assertIn(r'<tr><th>Slug</th><td>example</td></tr>', reply)
		self.assertIn(r'<tr><th>Versions</th><td>DMW</td></tr>', reply)
