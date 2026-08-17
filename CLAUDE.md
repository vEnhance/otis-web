# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

OTIS-WEB is a Django-based course management system for OTIS.
The production server is hosted on PythonAnywhere.

## Tech Stack

- **Framework**: Django 6.0+
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

#### What to assert on

Do not assert on rendered template prose. Rewording a message should never break
a test. Reach for these in order:

1. **`assert resp.context[...]`** — for what the view computed. Views already put
   the interesting values in the context (`level_number`, `rows`, `pset`,
   `object_list`, `title`), so assert on those directly.
2. **A direct database read** — for what a POST actually wrote. Assert on the
   model, not on the confirmation page that gets rendered afterwards.
3. **`otis.assert_testid(resp, "...")`** — for whether an element is visible to
   this user. Add a `data-testid` attribute to the template and assert on that,
   never on the surrounding wording or Bootstrap classes. Add one only where a
   test needs it.

`assert_has` / `assert_not_has` search the raw response bytes, which makes them
both brittle and often weak (`assert_has(resp, 38)` matches any pk or date
containing those digits). Keep them for the two cases where the bytes really are
the contract:

- **Leakage checks** — asserting secret content is *absent* from a page.
- **Views whose output is text** — the mailing-list and export views, where the
  rendered text is the product.

`dashboard/tests.py` is the worked example of this style.

Asserting on `messages` text is fine when the string is a fixed literal — it
lives in `views.py` next to the code you're editing, so a reword breaks one
obvious test. But do **not** assert on a message that interpolates a value; that
couples the test to a model's `__str__` or to float formatting. Assert the state
change instead, plus the level if it matters that the user was notified:

```python
assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])
```

Import it as `from django.contrib.messages import constants as message_levels` —
`messages` is already a common local variable name in these test files.

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
