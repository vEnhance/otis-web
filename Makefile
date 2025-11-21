.PHONY: help install runserver migrate migrations createsuperuser check test fmt prek

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make runserver        - Run Django development server"
	@echo "  make migrate          - Apply database migrations"
	@echo "  make migrations       - Create new migrations"
	@echo "  make createsuperuser  - Create a Django superuser"
	@echo "  make check            - Run Django checks and type checking"
	@echo "  make test             - Run tests with coverage"
	@echo "  make fmt              - Run code formatter"
	@echo "  make prek             - Run prek on all files"

install:
	uv sync
	uv run prek install

runserver:
	uv run python manage.py runserver_plus

migrate:
	uv run python manage.py migrate

migrations:
	@files=$$(uv run python manage.py makemigrations | grep -oP 'migrations/\S+\.py' | tr '\n' ' '); \
	if [ -n "$$files" ]; then uv run prek run --files $$files; fi

createsuperuser:
	uv run python manage.py createsuperuser

check:
	uv run python manage.py check
	uv run python manage.py validate_templates
	uv run pyright .

test:
	uv run coverage run -m pytest -n auto --cov --cov-report=term-missing

fmt:
	uv run prek run --all-files

prek:
	uv run prek run --all-files
