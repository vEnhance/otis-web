#!/bin/bash

python manage.py migrate
python manage.py loaddata fixtures/all.json
