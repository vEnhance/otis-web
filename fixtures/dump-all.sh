#!/bin/bash

python manage.py dumpdata --indent 2 --format json -e sessions -e admin -e contenttypes >fixtures/all.json
prettier -w fixtures/all.json
