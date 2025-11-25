.PHONY: help install runserver migrate migrations fmt check test ci copier

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make runserver        - Run Django development server"
	@echo "  make migrate          - Apply database migrations"
	@echo "  make migrations       - Create new migrations"
	@echo "  make fmt              - Run code formatter"
	@echo "  make check            - Run Django checks and type checking"
	@echo "  make test             - Run tests"
	@echo "  make ci               - Short for fmt + check + test"
	@echo "  make copier           - Run copier update with past answers"

install:
	uv sync
	uv run prek install

runserver:
	uv run python manage.py runserver_plus

migrate:
	uv run python manage.py migrate

migrations:
	files=$$(uv run python manage.py makemigrations --scriptable) && \
	if [ -n "$$files" ]; then \
		uv run prek run --files $$files; \
	fi

fmt:
	uv run prek run --all-files

check:
	uv run python manage.py check
	uv run python manage.py validate_templates
	uv run python manage.py makemigrations --check --dry-run
	uv run pyright .

test:
	uv run pytest -n auto --cov --cov-report=term-missing --cov-report=lcov:coverage/lcov.info

ci:
	make fmt
	make check
	make test

copier:
	uv run copier update --skip-answered
