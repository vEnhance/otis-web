from django.contrib.auth import get_user_model
from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory, FileField
from factory.faker import Faker

from core.factories import SemesterFactory, UnitFactory
from otisweb_testsuite import UniqueFaker
from roster.factories import StudentFactory

from .models import Announcement, PSet, SemesterDownloadFile, UploadedFile

User = get_user_model()


class UploadedFileFactory(DjangoModelFactory):
    class Meta:
        model = UploadedFile

    benefactor = SubFactory(StudentFactory)
    owner = LazyAttribute(lambda o: o.benefactor.user)
    category = "psets"
    content = FileField(filename="TESTING_pset.txt")
    unit = SubFactory(UnitFactory)


class SemesterDownloadFileFactory(DjangoModelFactory):
    class Meta:
        model = SemesterDownloadFile

    semester = SubFactory(SemesterFactory)
    description = "Announcement Description"
    content = FileField(filename="TESTING_announcement.txt")


class PSetFactory(DjangoModelFactory):
    class Meta:
        model = PSet

    student = SubFactory(StudentFactory)
    unit = SubFactory(UnitFactory)
    upload = LazyAttribute(
        lambda o: UploadedFileFactory.create(benefactor=o.student, unit=o.unit)
    )
    next_unit_to_unlock = SubFactory(UnitFactory)
    status = "A"


class AnnouncementFactory(DjangoModelFactory):
    class Meta:
        model = Announcement

    subject = Faker("bs")
    slug = UniqueFaker("slug")
    content = Faker("paragraph")
