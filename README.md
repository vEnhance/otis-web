[<img src="https://img.shields.io/github/languages/top/vEnhance/otis-web" alt="Top languages">](https://img.shields.io/github/languages/top/vEnhance/otis-web)
[<img src="https://img.shields.io/github/license/vEnhance/otis-web" alt="MIT License">](https://github.com/vEnhance/otis-web/blob/main/LICENSE.txt)
[<img src="https://img.shields.io/github/last-commit/vEnhance/otis-web" alt="Last update">](https://img.shields.io/github/last-commit/vEnhance/otis-web)
<img src="https://img.shields.io/github/forks/vEnhance/otis-web" alt="Forks">
<img src="https://img.shields.io/github/stars/vEnhance/otis-web" alt="Stars">
[<img src="https://github.com/vEnhance/otis-web/actions/workflows/ci.yml/badge.svg" alt="OTIS-WEB status">](https://github.com/vEnhance/otis-web/actions)
[<img src="https://github.com/vEnhance/otis-web/actions/workflows/codeql-analysis.yml/badge.svg" alt="OTIS-WEB status">](https://github.com/vEnhance/otis-web/actions)

[<img src="https://img.shields.io/badge/html-djlint-blueviolet.svg" alt="djlint">](https://www.djlint.com)
[<img src="https://img.shields.io/badge/python%20style-black-000000.svg" alt="style: black">](https://github.com/psf/black)
[<img src="https://img.shields.io/badge/types-pyright-00cca7.svg" alt="types: pyright">](https://github.com/PyCQA/pyflakes)
[<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="lint: ruff">](https://github.com/astral-sh/ruff)
[<img src="https://coveralls.io/repos/github/vEnhance/otis-web/badge.svg?branch=main" alt="Coverage status">](https://coveralls.io/github/vEnhance/otis-web?branch=main)

# OTIS-WEB

These are the source files for the internal website
that I use to teach my course [OTIS](https://web.evanchen.cc/otis.html).
It is pretty standard Django, so you should be able to spin
up a local server on a standard Unix environment.

## Installation instructions

Video tutorial: https://youtu.be/W27XcqeXp20

### Standard Linux environment

If you're just trying to get a local copy of the OTIS-WEB code
and don't plan to submit any code back, then skip steps 0 and 4,
and replace `YOUR_USERNAME` in step 2 with `vEnhance`.

0. Create an account on GitHub if you haven't already, and
   [fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo).
1. Install the following standard tools: `python` (version 3.10), `pip`, `git`.
   (For each tool, search "[name of thing to install] [your OS]" on the web.)
2. Clone this repository using the command
   `git clone https://github.com/YOUR_USERNAME/otis-web`.
3. Run `git submodule update --init --recursive`
   in order to pull the `evans_django_tools` submodule.
4. Type `git checkout -b feature` to checkout a new branch named `feature`;
   this will make your life a bit easier than working on `main`.
   If you already know what feature you're trying to implement,
   you can use that, e.g. `git checkout -b add-bunny-pictures`.
5. [Install Poetry](https://python-poetry.org/docs/).
   This enables you to use the `poetry` command;
   verify this by checking `poetry --help` produces a help message.
6. Once you have `poetry`, hit `poetry install`.
   This will automatically create a
   Python virtual environment and install stuff inside it.
   (If you are an expert familiar with Python virtual environments
   and want to use your own rather than Poetry's auto-created one,
   then activate said environment before running `poetry install`.)

   On some systems, `poetry install` could fail when trying to install
   `mysqlclient`. You will have to separately install `pkg-config`
   [mysql](https://github.com/PyMySQL/mysqlclient#install) in that case;
   see that link for instructions, under the "Install" section.

7. If it isn't already activated,
   [activate the Python virtual environment][activate]
   that was created in the previous step.
   The easiest way to do so is to run `poetry shell`.

   (_Note_: you have to do this step every time you start working on the
   project. That is, always run `poetry shell` before doing any work, or
   for experts, activate the virtual environment using your preferred method.)

8. If everything is working, `python manage.py check` should
   run with no errors.
9. Run `python manage.py migrate` to create the local database.
10. Run `python manage.py createsuperuser` to create an admin user.
11. Run `python manage.py runserver`.
    The command will spin up a continuously running server.
12. Point your browser to `http://127.0.0.1:8000`.
    You should be able to log in with the user you defined in step 9.
13. The website is functional now, but it is a bit bare-bones.
    To populate it with some test data, use `http://127.0.0.1:8000/admin`
    or run `./fixtures/load-all.sh`.

[activate]: https://python-poetry.org/docs/basic-usage/#activating-the-virtual-environment

Optional steps:

- If you need to set up environment variables,
  copy `env` to `.env` and uncomment the relevant lines.
- If you want to test the Stripe stuff, a few more steps are needed.
  Briefly: install the Stripe CLI.
  Create some API keys and `stripe login`.
  Add these API keys to `.env` (the three `STRIPE_*` variables).
  Then run `stripe listen --forward-to localhost:8000/payments/webhook/`.

[venv]: https://djangocentral.com/how-to-a-create-virtual-environment-for-python/

### Using Docker

0. Follow steps 0 - 3 from the above tutorial.
1. Make sure to install [Docker](https://www.docker.com/) and make sure you
   download a version compatible with your computer.
2. Set up the 3 environment variables at the bottom of `env` by copying them to
   `.env` and uncommenting them. Note that you should not have any spaces (it is
   fine to leave the values as it is, but if you want to change anything, just
   make sure there is no whitespace surrounding the `=`).
3. Run `docker compose build`. Wait for it to finish.
4. To start the server, run `docker compose up -d`. To execute a command inside
   the container, run `docker exec -it otis-web /bin/bash`. To stop the server,
   run `docker compose down`.
5. Follow steps 11 - 12 from above.

Note: You may need to delete db.sqlite3 if you're not getting desired results,
as it serves as a cache. At this point, spinning up 2 separate containers with
separate data stores is not supported.

## Feature requests or bug reports

Submit an [issue on GitHub](https://github.com/vEnhance/otis-web/issues).

## Pull requests

For OTIS students: pull requests welcome!
If you think the website can be improved in some way, feel free to implement it.
See [contributing guidelines](CONTRIBUTING.md).
It's OK if you don't have much code experience; I'm willing to guide you along.

`526561645265616452656164`
