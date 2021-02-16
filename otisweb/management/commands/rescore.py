from django.core.management.base import BaseCommand, CommandError
from roster.models import Student
from django.db.models import Count, Q, F, Subquery, OuterRef

from roster.models import Student
from dashboard.models import UploadedFile

class Command(BaseCommand):
	help = 'Recalculates the number of problem sets completed by each student'


	def handle(self, *args, **options):
#		students = Student.objects.annotate(num_psets = Subquery(
#			UploadedFile.objects.filter(category='psets', benefactor=OuterRef('id'))\
#					.annotate(n = Count('unit', distinct=True)).values('n')))
#
#		Student.objects.update(num_units_done = Subquery(
#			Student.objects.annotate(n = Count('uploadedfile__unit',
#			filter = Q(uploadedfile__category='psets'), distinct = True))\
#				.filter(id = OuterRef('id')).values('n')))

		students = list(Student.objects.annotate(num_psets = Count('uploadedfile__unit',
				filter=Q(uploadedfile__category='psets'), distinct=True)))

		for s in students:
			s.num_units_done = s.num_psets

		Student.objects.bulk_update(students, ['num_units_done',], batch_size = 100)

