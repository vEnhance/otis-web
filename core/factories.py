import random
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from factory import Faker, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from factory.helpers import post_generation
from otisweb.testsuite import UniqueFaker

from core.models import Semester, Unit, UnitGroup, UserProfile
from core.utils import storage_hash

User = get_user_model()


class UserFactory(DjangoModelFactory):
	class Meta:
		model = User

	first_name = Faker('first_name_female')
	last_name = Faker('last_name_female')
	username = UniqueFaker('pystr', min_chars=30, max_chars=40, prefix='user_')
	email = Faker('ascii_safe_email')


class UnitGroupFactory(DjangoModelFactory):
	class Meta:
		model = UnitGroup

	name = UniqueFaker('bs')
	slug = UniqueFaker('slug')
	description = Faker('catch_phrase')
	subject = FuzzyChoice(UnitGroup.SUBJECT_CHOICES)


class UnitFactory(DjangoModelFactory):
	class Meta:
		model = Unit

	code = LazyAttribute(
		lambda o: random.choice('BDZ') + o.group.subject[0] + random.choice('WXY')
	)
	group = SubFactory(UnitGroupFactory)
	position = Sequence(lambda n: n + 1)

	@post_generation
	def write_mock_media(self, create: bool, extracted: bool, **kwargs: Dict[str, Any]):
		assert settings.TESTING is True
		if settings.TESTING_NEEDS_MOCK_MEDIA is False:
			return
		u: Unit = self  # type: ignore
		stuff_to_write = [
			(u.problems_pdf_filename, b'Prob', ".pdf"),
			(u.solutions_pdf_filename, b'Soln', ".pdf"),
			(u.problems_tex_filename, b'TeX', ".tex"),
		]
		for (fname, content, ext) in stuff_to_write:
			default_storage.save('pdfs/' + storage_hash(fname) + ext, ContentFile(content))


class SemesterFactory(DjangoModelFactory):
	class Meta:
		model = Semester

	name = Sequence(lambda n: f"Year {n + 1}")
	active = True
	exam_family = 'Waltz'
	gradescope_key = 'ABCDEF'
	social_url = 'https://instagram.com/evanchen.cc/'


class UserProfileFactory(DjangoModelFactory):
	class Meta:
		model = UserProfile

	user = SubFactory(UserFactory)
