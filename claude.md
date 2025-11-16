# OTIS-WEB

Course management system for OTIS (Olympiad Training for Improving Scholars), a competitive mathematics program taught by Evan Chen.

## Tech Stack

- **Backend:** Django 5.2, Python 3.13+
- **Database:** MySQL
- **Frontend:** Bootstrap 5, Django templates
- **Package Management:** Poetry
- **Code Quality:** prek (pre-commit hooks)
- **Submodule:** `evans_django_tools` (shared utilities)

## Project Structure

```
otisweb/           # Django project config (settings.py, urls.py)
core/              # Core models (Semester, Unit, UserProfile)
roster/            # Student enrollment (Student, Assistant, Invoice)
dashboard/         # Problem sets (PSet, UploadedFile)
exams/             # Practice exams
payments/          # Stripe payment processing
rpg/               # Achievements and gamification
aincrad/           # Leveling system
opal/              # Hunt/achievement hunts
arch/              # Architecture problems
markets/           # Market system
suggestions/       # Student suggestions
hanabi/            # Hanabi game
mouse/             # Mouse system
tubes/             # Tube system
wikihaxx/          # Wiki extensions
fixtures/          # Test data (load with ./fixtures/load-all.sh)
```

## Development Commands

All commands are available via Make:

```bash
make help                   # Show all available commands

# Setup
make install                # Install dependencies and prek hooks
git submodule update --init # Initialize evans_django_tools

# Database
make migrate                # Apply migrations
make makemigrations         # Create new migrations
make createsuperuser        # Create admin user
./fixtures/load-all.sh      # Load test data

# Server
make runserver              # Start development server (runserver_plus)

# Testing & Code Quality
make test                   # Run tests with coverage
make check                  # Run Django checks and pyright type checking
make fmt                    # Format all code (via prek)
make prek                   # Run all prek hooks on all files
```

## Code Style

- **Python:** Use type annotations (enforced by pyright), follow Google style guide
- **Formatting:** `ruff format` for Python, `djlint` for templates, `prettier` for CSS/JS
- **Linting:** `ruff check` catches common issues, `codespell` for spelling
- **Templates:** 2-space indentation, Bootstrap 5 classes
- **Commits:** Conventional commits enforced (feat, fix, docs, etc.)
- Run `make fmt` or `make prek` before committing (hooks auto-run on commit/push)

## Testing

- Tests live in `*/tests.py` files in each app
- Use `factory_boy` for test data (factories in `*/factories.py`)
- Base class: `EvanTestCase` from `evans_django_tools.testsuite`
- Common assertions: `assertGet20X()`, `assertGetDenied()`, `assertPost20X()`
- All PRs must pass CI checks (GitHub Actions)
- Pre-push hooks run `make check`, `make test`, and `make fmt`

## Key Files

- `otisweb/settings.py` - Django configuration
- `pyproject.toml` - Dependencies and tool configs
- `Makefile` - Development commands
- `.pre-commit-config.yaml` - prek/pre-commit hook configuration
- `env` - Environment variable template (copy to `.env`)

## Environment Variables

Key variables (see `env` file for full list):

- `DJANGO_SECRET_KEY` - Required for Django
- `DATABASE_*` - MySQL connection settings
- `STRIPE_*` - Payment processing keys
- `IS_PRODUCTION` - Enable production mode
