#!/bin/bash

if [ -e db.sqlite3 ]
then
  :
else
  . ./.env
  uv run python manage.py migrate
  uv run python manage.py createsuperuser --no-input
fi

if [ "$SETUP" = "1" ]
then
  :
else
  uv run python manage.py runserver 0.0.0.0:8000
fi
