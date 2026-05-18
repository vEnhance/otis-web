#!/bin/bash

cd "$(git rev-parse --show-toplevel)" || exit
uv run python manage.py migrate
uv run python manage.py loaddata fixtures/core.UnitGroup.json
uv run python manage.py loaddata fixtures/core.Unit.json
uv run python manage.py loaddata fixtures/rpg.Level.json
uv run python fixtures/populate.py
