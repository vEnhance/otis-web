from core.factories import SemesterFactory, UnitFactory, UserFactory
from django.contrib.auth import get_user_model
from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from roster.models import Assistant, Invoice, RegistrationContainer, Student, StudentRegistration, UnitInquiry  # NOQA

User = get_user_model()


class AssistantFactory(DjangoModelFactory):
	class Meta:
		model = Assistant

	user = SubFactory(UserFactory, is_staff=True)
	shortname = LazyAttribute(lambda o: o.user.first_name)


class StudentFactory(DjangoModelFactory):
	class Meta:
		model = Student

	user = SubFactory(UserFactory)
	semester = SubFactory(SemesterFactory)
	track = 'C'
	newborn = False
	last_level_seen = 0


class InvoiceFactory(DjangoModelFactory):
	class Meta:
		model = Invoice

	student = SubFactory(StudentFactory)
	preps_taught = 2


class UnitInquiryFactory(DjangoModelFactory):
	class Meta:
		model = UnitInquiry

	student = SubFactory(StudentFactory)
	unit = SubFactory(UnitFactory)
	action_type = "UNLOCK"
	explanation = Faker('sentence')


class RegistrationContainerFactory(DjangoModelFactory):
	class Meta:
		model = RegistrationContainer

	semester = SubFactory(SemesterFactory)
	passcode = Faker('color_name')
	allowed_tracks = 'C,'


class StudentRegistrationFactory(DjangoModelFactory):
	class Meta:
		model = StudentRegistration

	user = SubFactory(UserFactory)
	container = SubFactory(RegistrationContainerFactory)
	parent_email = Faker('ascii_safe_email')
	track = 'C'
	gender = 'H'
	graduation_year = 0
	school_name = Faker('city')
