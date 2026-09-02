# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

OTIS-WEB is a Django-based course management system for OTIS.
The production server is hosted on PythonAnywhere.

`README.md` covers installation and `CONTRIBUTING.md` covers the human-facing
workflow; this file only adds what is specific to working here as an agent.

## Tech Stack

- **Framework**: Django 6.0 (pinned `>=6.0.7,<6.1.0`)
- **Python**: 3.13+
- **Package manager**: uv
- **Database**: SQLite (dev), MySQL (prod)
- **Type checking**: pyright
- **Testing**: pytest with pytest-django, pytest-xdist, factory-boy, freezegun, coverage
- **Hooks**: prek (a pre-commit reimplementation), configured in `prek.toml`
- **Formatters/linters**: ruff (Python), djlint (templates), prettier (CSS/JS/JSON/YAML),
  rumdl (Markdown), codespell, shellcheck and shfmt (shell), zizmor (workflows)

## Common Commands

```bash
make install          # Install dependencies and git hooks
make runserver        # Run Django development server (runserver_plus)
make createsuperuser  # Create an admin user
make migrate          # Apply database migrations
make migrations       # Create new migrations, then format them
make check            # Django checks, template validation, missing-migration check, pyright
make test             # Run tests with coverage
make fmt              # Run all formatters and linters via prek
make ci               # fmt + check + test, i.e. everything GitHub Actions runs
```

`make fmt` rewrites files in place, so re-read anything you had open afterwards.

The pre-push hook runs `make fmt`, `make check`, and `make test`, so a push
takes a few minutes and fails loudly rather than pushing broken code.

## Project Structure

```text
otisweb/            Project settings, URLs, shared mixins and decorators
otisweb_testsuite/  The `otis` test fixture and faker helpers
core/               Semesters, units, unit groups, user profiles
roster/             Students, assistants, invoices, unit petitions, registration
dashboard/          Student portal: problem set uploads, announcements, downloads
arch/               Problem archive: statements, hints, votes
exams/              Practice exams, quizzes, mock attempts
rpg/                Achievements, levels, quests, palace carvings
payments/           Stripe integration and worker job board
suggestions/        Student-submitted problem suggestions
tubes/              Testsolving containers, plus OIME proposals and voting
opal/               OPAL puzzle hunts
hanabi/             hanab.live contests and replays
markets/            Estimation markets and guesses
yearbook/           Student yearbook entries
mouse/              USEMO scoring and grader pages
aincrad/            JSON API endpoints for external scripts (token-authenticated)
```

## Development Guidelines

### Code Style

- Follow Google's Python style guide
- Use type annotations for function parameters and return types
- Run `make fmt` before committing and `make check` to verify types

### Commits

The `commit-msg` hook enforces Conventional Commits. The type must be one of:

```text
feat fix build ci chore docs drop edit perf polish
root refactor revert style temp tests
```

A scope is usually the app name, e.g. `feat(roster): add applicant_name field`.
Append `!` for a breaking change: `refactor(roster)!: rename UnitInquiry`.

### Pull Requests

**Leave the PR body empty.** Evan rewrites it anyway, so generating one is
wasted effort. The title still matters — it becomes the squashed commit message,
so it must follow the commit conventions above.

### Testing

Tests are plain pytest functions in `*/tests.py`, marked `@pytest.mark.django_db`
and built from the per-app `factories.py`. The `otis` fixture
(`otisweb_testsuite/fixtures.py`) wraps the Django test client with `login`,
`get_ok`/`post_redirects`-style helpers, and the assertions below.
`dashboard/tests.py` is the worked example. `make test` runs them in parallel with
`--reuse-db`, so after adding a migration run `uv run pytest --create-db` once to
rebuild the cached test database.

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

- Use `make migrations` to create new migrations and `make migrate` to apply them
- `make check` fails if a model change has no migration
- Fixtures are in `fixtures/`; load them with `./fixtures/load-all.sh`

### Environment Variables

- Copy `env` to `.env` and uncomment what you need
- Only required for optional integrations (Stripe, Discord webhooks, cloud storage)

## Type Checking Notes

The codebase is heavily type-checked with pyright. Key settings in `pyproject.toml`:

- `typeCheckingMode = "basic"`, with many individual rules raised to `"error"`
- Migrations and test files are excluded from type checking
- Django stubs are installed for better type inference
