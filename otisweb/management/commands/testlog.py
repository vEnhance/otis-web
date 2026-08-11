import logging
from typing import Any

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Try logging"

    def handle(self, *args: Any, **options: Any):
        """Try logging a message"""
        try:
            raise ValueError("AHHHH THE WORLD IS ON FIRE")
        except ValueError as e:
            logger.error(str(e))
