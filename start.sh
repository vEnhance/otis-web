. ./.env

poetry run python manage.py migrate
poetry run python manage.py createsuperuser --no-input
poetry run python manage.py runserver 0.0.0.0:8000