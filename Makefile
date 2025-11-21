.PHONY: help install runserver migrate makemigrations createsuperuser check test fmt prek-install prek

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with poetry"
	@echo "  make runserver        - Run Django development server"
	@echo "  make migrate          - Apply database migrations"
	@echo "  make makemigrations   - Create new migrations"
	@echo "  make createsuperuser  - Create a Django superuser"
	@echo "  make check            - Run Django checks and type checking"
	@echo "  make test             - Run tests"
	@echo "  make fmt              - Run code formatter"
	@echo "  make prek-install     - Install prek hooks"
	@echo "  make prek             - Run prek on all files"

install:
	poetry install --all-groups
	poetry run prek install

runserver:
	poetry run python manage.py runserver_plus

migrate:
	poetry run python manage.py migrate

makemigrations:
	poetry run python manage.py makemigrations

createsuperuser:
	poetry run python manage.py createsuperuser

check:
	poetry run python manage.py check
	poetry run python manage.py validate_templates
	poetry run pyright .

test:
	poetry run coverage run -m pytest -n auto

fmt:
	poetry run prek run --all-files

prek-install:
	poetry run prek install

prek:
	poetry run prek run --all-files
