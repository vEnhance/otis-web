# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

OTIS-WEB is a Django-based course management system for OTIS (Online Training for International Students), a math olympiad training program. The production server is hosted on PythonAnywhere.

## Tech Stack

- **Framework**: Django 5.2+
- **Python**: 3.13+
- **Package Manager**: uv
- **Database**: SQLite (dev), MySQL (prod)
- **Type Checking**: pyright
- **Linting/Formatting**: ruff, djlint
- **Testing**: pytest with pytest-django, pytest-xdist, coverage

## Common Commands

```bash
make install          # Install dependencies with uv
make runserver        # Run Django development server
make migrate          # Apply database migrations
make migrations       # Create new migrations
make check            # Run Django checks and pyright type checking
make test             # Run tests with coverage
make fmt              # Run code formatters (prek)
```

## Project Structure

Key Django apps:

- `core/` - Core models and utilities
- `dashboard/` - Student dashboard
- `roster/` - Student roster management
- `exams/` - Exam management
- `arch/` - Problem archive
- `payments/` - Stripe payment integration
- `rpg/` - Achievement/gamification system
- `wiki/` - Wiki integration
- `otisweb/` - Main project settings

## Development Guidelines

### Code Style

- Follow Google's Python style guide
- Use type annotations for function parameters and return types
- Run `make fmt` before committing to auto-format code
- Run `make check` to verify type checking passes

### Testing

- Write tests for any new functionality in `*/tests.py` files
- Run `make test` to execute tests with coverage
- Tests use pytest with the `--reuse-db` flag for speed

### Database

- Use `make migrations` to create new migrations
- Use `make migrate` to apply migrations
- Fixtures are in `fixtures/` directory; load with `./fixtures/load-all.sh`

### Environment Variables

- Copy `env` to `.env` and configure as needed
- Required for Stripe integration and other optional features

## Type Checking Notes

The codebase is heavily type-checked with pyright. Key settings:

- `typeCheckingMode = "basic"`
- Migrations and test files are excluded from type checking
- Django stubs are installed for better type inference
