[<img src="https://img.shields.io/github/languages/top/vEnhance/otis-web" alt="Top languages">](https://img.shields.io/github/languages/top/vEnhance/otis-web)
[<img src="https://img.shields.io/github/license/vEnhance/otis-web" alt="MIT License">](https://github.com/vEnhance/otis-web/blob/main/LICENSE.txt)
[<img src="https://img.shields.io/github/last-commit/vEnhance/otis-web" alt="Last update">](https://img.shields.io/github/last-commit/vEnhance/otis-web)
<img src="https://img.shields.io/github/forks/vEnhance/otis-web" alt="Forks">
<img src="https://img.shields.io/github/stars/vEnhance/otis-web" alt="Stars">
[<img src="https://github.com/vEnhance/otis-web/actions/workflows/ci.yml/badge.svg" alt="OTIS-WEB status">](https://github.com/vEnhance/otis-web/actions)
[<img src="https://github.com/vEnhance/otis-web/actions/workflows/codeql-analysis.yml/badge.svg" alt="OTIS-WEB status">](https://github.com/vEnhance/otis-web/actions)

[<img src="https://img.shields.io/badge/html-djlint-blueviolet.svg" alt="HTML style: djlint">](https://www.djlint.com)
[<img src="https://img.shields.io/badge/python%20style-black-000000.svg" alt="Python style: black">](https://github.com/psf/black)
[<img src="https://img.shields.io/badge/types-pyright-00cca7.svg" alt="types: pyright">](https://github.com/PyCQA/pyflakes)
[<img src="https://img.shields.io/badge/types-mypy-00cca7.svg" alt="types: mypy">](http://mypy-lang.org/)
[<img src="https://img.shields.io/badge/lint-pyflakes-ff69b4.svg" alt="lint: pyflakes">](https://github.com/PyCQA/pyflakes)
[<img src="https://coveralls.io/repos/github/vEnhance/otis-web/badge.svg?branch=main" alt="Coverage status">](https://coveralls.io/github/vEnhance/otis-web?branch=main)

# OTIS-WEB

These are the source files for the internal website
that I use to teach my course [OTIS](https://web.evanchen.cc/otis.html).
It is pretty standard Django, so you should be able to spin
up a local server on a standard Unix environment.

## Installation instructions

Video tutorial: https://youtu.be/W27XcqeXp20

### Standard Linux environment

0. [Fork the repository first](https://docs.github.com/en/get-started/quickstart/fork-a-repo)
   if you're planning on submitting a pull request later.
1. Install the following standard tools: `python` (version 3.10), `pip`, `git`.
   (For each tool, search "[name of thing to install] [your OS]" on the web.)
2. Clone this repository:
   `git clone https://github.com/USERNAME/otis-web`.
   Replace `USERNAME` with your username if you're forking;
   otherwise, replace with `vEnhance`.
3. Run `git submodule update --init --recursive`
   in order to pull the `evans_django_tools` submodule.
4. You probably want to create a new virtual environment
   to avoid polluting your system with all the dependencies.
   If you've used `conda` or `virtualenv` or similar before, you know the drill.
   Otherwise, [read through the steps here][venv] to create a wrapper for OTIS-WEB.
5. If things are working, you should be able to run in the virtual environment
   and then [install Poetry](https://python-poetry.org/docs/).
   This enables you to use the `poetry` command;
   verify this by checking `poetry --help` produces a help message.
6. Once you have `poetry`, hit `poetry install`.
   This will install a lot of Python packages into your virtual environment.
7. If everything is working, `python manage.py check` should
   run with no errors.
8. Run `python manage.py migrate` to create the local database.
9. Run `python manage.py createsuperuser` to create an admin user.
10. Run `python manage.py runserver`.
    The command will spin up a continuously running server.
11. Point your browser to `http://127.0.0.1:8000`.
    You should be able to log in with the user you defined in step 9.
12. The website is functional now, but it is a bit bare-bones.
    To populate it with some test data, use `http://127.0.0.1:8000/admin`.

Optional steps:

- If you need to set up environment variables,
  copy `env` to `.env` and uncomment the relevant lines.
- If you want to test the Stripe stuff, a few more steps are needed.
  Briefly: install the Stripe CLI.
  Create some API keys and `stripe login`.
  Add these API keys to `.env` (the three `STRIPE_*` variables).
  Then run `stripe listen --forward-to localhost:8000/payments/webhook/`.

[venv]: https://djangocentral.com/how-to-a-create-virtual-environment-for-python/

## Feature requests or bug reports

Submit an [issue on GitHub](https://github.com/vEnhance/otis-web/issues).

## Pull requests

For OTIS students: pull requests welcome!
If you think the website can be improved in some way, feel free to implement it.
See [contributing guidelines](CONTRIBUTING.md).
It's OK if you don't have much code experience; I'm willing to guide you along.

`526561645265616452656164`
