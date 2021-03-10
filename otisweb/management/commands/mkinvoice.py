from django.core.management.base import BaseCommand, CommandError
import core.models
import roster.models

class Command(BaseCommand):
	help = "Creates invoices for all the students in the active semester without an active invoice"

	def add_arguments(self, parser):
		parser.add_argument('preps',
				type=int,
				help="Number of preps taught")

	def handle(self, *args, **options):
		semester = core.models.Semester.objects.get(active = True) # crash if > 1 semester
		students = roster.models.Student.objects.filter(semester = semester, invoice__isnull=True)

		invoices = []
		for s in students:
			invoices.append(roster.models.Invoice(student = s, \
				preps_taught = options['preps'], \
				hours_taught = 8.4 if (s.track == 'A' or s.track == 'B') else 0, \
				))
		print(f"Created {len(invoices)} invoices")
		roster.models.Invoice.objects.bulk_create(invoices)
