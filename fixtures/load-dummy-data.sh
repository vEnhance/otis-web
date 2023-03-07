#!/bin/bash

python manage.py loaddata fixtures/core.UnitGroup.json
python manage.py loaddata fixtures/core.Unit.json
python manage.py loaddata fixtures/rpg.Level.json
python fixtures/populate.py
