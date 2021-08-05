from django.core.management.base import BaseCommand, CommandError

from core.models import Unit
from dashboard.models import UploadedFile
from roster.models import Student


class Command(BaseCommand):
	help = 'Replaces all instances of unit X with unit Y'
	def add_arguments(self, parser):
		parser.add_argument('source', type=int, help="ID of source unit")
		parser.add_argument('dest', type=int, help="ID of destination unit")

	def handle(self, *args, **options):
		source_id = options.pop('source')
		dest_id = options.pop('dest')
		print(f"Deleting {Unit.objects.get(id=source_id)}")
		print(f"Replacing with {Unit.objects.get(id=dest_id)}")

		u = UploadedFile.objects.filter(unit=source_id)
		s1 = Student.objects.filter(curriculum=source_id)
		s2 = Student.objects.filter(unlocked_units=source_id)

		print(f"This will change {u.count()} uploaded files.")
		print(f"This will affect {s1.count()} students with the unit, of which {s2.count()} have it unlocked.")

		if input("Are you sure? ").strip().lower() != 'y':
			return

		u.update(unit=dest_id)
		for s in s1:
			s.curriculum.remove(source_id)
			s.curriculum.add(dest_id)
		for s in s2:
			s.unlocked_units.remove(source_id)
			s.unlocked_units.add(dest_id)
