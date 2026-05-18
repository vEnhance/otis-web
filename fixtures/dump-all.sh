#!/bin/bash

cd "$(git rev-parse --show-toplevel)" || exit
uv run python manage.py dumpdata --indent 2 --format json -e sessions -e admin -e contenttypes >fixtures/all.json
prettier -w fixtures/all.json
