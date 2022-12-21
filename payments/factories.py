from core.factories import UserFactory
from evans_django_tools.testsuite import UniqueFaker
from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from roster.factories import InvoiceFactory

from payments.models import Job, JobFolder, PaymentLog, Worker


class PaymentLogFactory(DjangoModelFactory):
    class Meta:
        model = PaymentLog

    invoice = SubFactory(InvoiceFactory)
    amount = 0


class JobFolderFactory(DjangoModelFactory):
    class Meta:
        model = JobFolder

    name = Faker("sentence")
    slug = UniqueFaker("slug")


class WorkerFactory(DjangoModelFactory):
    class Meta:
        model = Worker

    user = SubFactory(UserFactory)


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    name = Faker("job")
    folder = SubFactory(JobFolderFactory)
