import secrets
from argparse import ArgumentParser
from hashlib import sha256
from typing import Any

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from aincrad.auth import READONLY_ACTIONS

SETTING_NAMES = {
    "full": "API_TOKEN_HASH_FULL",
    "readonly": "API_TOKEN_HASH_READONLY",
}


class Command(BaseCommand):
    help = "Generates an aincrad API token and the hash to configure it with"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            "scope",
            choices=sorted(SETTING_NAMES),
            help=f"full access, or read-only ({', '.join(sorted(READONLY_ACTIONS))})",
        )
        parser.add_argument(
            "--pbkdf2",
            action="store_true",
            help="hash with Django's password hasher instead of plain SHA-256; "
            "safer for a short token, but costs about a second per request",
        )

    def handle(self, *args: Any, **options: Any):
        del args
        token = secrets.token_urlsafe(32)
        if options["pbkdf2"]:
            token_hash = make_password(token)
        else:
            token_hash = sha256(token.encode("utf-8")).hexdigest()

        print(f"Token (give this to the client, it is not stored anywhere):\n{token}\n")
        print("Hash (put this in the environment):")
        print(f'{SETTING_NAMES[options["scope"]]}="{token_hash}"')
