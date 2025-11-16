# OTIS-WEB

Course management system for OTIS (Olympiad Training for Improving Scholars), a competitive mathematics program taught by Evan Chen.

## Tech Stack

- **Backend:** Django 5.2, Python 3.13+
- **Database:** MySQL
- **Frontend:** Bootstrap 5, Django templates
- **Package Management:** Poetry
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

```bash
# Setup
poetry install                    # Install dependencies
poetry shell                      # Activate virtual environment
git submodule update --init       # Initialize evans_django_tools

# Database
python manage.py migrate          # Apply migrations
python manage.py makemigrations   # Create new migrations
python manage.py createsuperuser  # Create admin user
./fixtures/load-all.sh            # Load test data

# Server
python manage.py runserver        # Start development server

# Testing
python manage.py test             # Run all tests
python manage.py test roster      # Test specific app
coverage run manage.py test       # Run with coverage report

# Code Quality (run all with ./lint.sh)
ruff check --fix                  # Lint and auto-fix Python
ruff format                       # Format Python code
djlint --reformat .               # Format Django templates
pyright                           # Type checking
codespell                         # Spell checking
```

## Code Style

- **Python:** Use type annotations (enforced by pyright), follow Google style guide
- **Formatting:** `ruff format` for Python, `djlint` for templates
- **Linting:** `ruff check` catches common issues
- **Templates:** 2-space indentation, Bootstrap 5 classes
- Run `./lint.sh` before committing (or set up as pre-commit hook)

## Testing

- Tests live in `*/tests.py` files in each app
- Use `factory_boy` for test data (factories in `*/factories.py`)
- Base class: `EvanTestCase` from `evans_django_tools.testsuite`
- Common assertions: `assertGet20X()`, `assertGetDenied()`, `assertPost20X()`
- All PRs must pass CI checks (GitHub Actions)

## Key Files

- `otisweb/settings.py` - Django configuration
- `pyproject.toml` - Dependencies and tool configs
- `env` - Environment variable template (copy to `.env`)
- `lint.sh` - Run all code quality checks
- `autofix.sh` - Auto-format all code

## Environment Variables

Key variables (see `env` file for full list):

- `DJANGO_SECRET_KEY` - Required for Django
- `DATABASE_*` - MySQL connection settings
- `STRIPE_*` - Payment processing keys
- `IS_PRODUCTION` - Enable production mode
