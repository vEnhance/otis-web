#!/bin/bash

cd "$(git rev-parse --show-toplevel)" || exit
uv run python manage.py migrate
uv run python manage.py loaddata fixtures/all.json
