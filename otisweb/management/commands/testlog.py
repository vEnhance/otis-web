import logging

from django.core.management.base import BaseCommand


class Command(BaseCommand):
	help = 'Try logging'

	def handle(self, *args, **options):
		"""Try logging a message"""
		try:
			raise ValueError("AHHHH THE WORLD IS ON FIRE")
		except ValueError as e:
			logging.error(str(e))
