#!/bin/bash

cd "$(git rev-parse --show-toplevel)" || exit
python manage.py migrate
python manage.py loaddata fixtures/all.json
