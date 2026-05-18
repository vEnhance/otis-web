#!/bin/sh

# If you aren't Evan, replace the bucket name...
uv run python manage.py collectstatic --noinput
gcloud storage rsync --recursive static/ gs://otisweb-static/static
