# Contributing guidelines

Thank you for your interest in contributing to the OTIS-WEB server!

Part of my agenda is to encourage my students to
[learn how to code](https://web.evanchen.cc/techsupport.html),
so consequently I want to be welcoming of people who are learning the ropes.
Don't feel shy! I am happy to help you get up to speed
and work with you as you pick things up.

## Video tutorial

If you prefer videos to text, see:

https://youtu.be/W27XcqeXp20

## Getting started

### Pre-reading

If you're totally new to development world,
it's probably a good idea to learn how a bunch of tools work.
[There's a nice series by MIT](https://missing.csail.mit.edu/) to this end.
You'll likely want to go through the first six of the 2020 lectures,
except possibly for the third one about Vim.
(I'm a die-hard Vim user myself, but I think it's too much to learn at once;
pick up Vim later.)

### Fork

Before you get started,
you will actually want to create your own _fork_ of OTIS-WEB.
This is a bit counter-intuitive,
but essentially the reason is that I own OTIS-WEB,
so if you want to make edits of any sort,
it has to be on a _copy_ owned by you first --- that's a fork.

Follow the
[fork instructions here](https://docs.github.com/en/get-started/quickstart/fork-a-repo).
When you're done, you should have your own copy
of OTIS-WEB owned by you,
that you can edit however you want.

### Installation

Follow the [README](README.md) instructions.

### Claiming tasks

If you haven't already, create a free account on [GitHub](https://github.com/).

The list of things to-do is sorted with two different views:

- The [Projects](https://github.com/vEnhance/otis-web/projects?query=is%3Aopen+sort%3Acreated-asc)
  view shows the set of tasks to do sorted by bounty.
- The [issues page](https://github.com/vEnhance/otis-web/issues)
  lists all the issues, including those with no bounty set yet.

To claim a task, you should go to the corresponding
and leave a comment that you'd like to work on it.
A moderator (well, Evan) will then assign the task to you.

Alternatively, you can also create a new issue if you have
an idea for a feature request or a bug to report.

## Writing the code

Now that you have an issue assigned to you, you can start working on it!
There will be a lot of poking around the website to understand
how things are working, and it may be overwhelming at first.
Don't sweat it too much.
Most tasks only require you to change small parts of the code,
which you can do in isolation while ignoring the other parts for now.

## Writing tests

You should write tests for any new functionality you add.
Read the files called `*/tests.py` and do as the Romans do.

It's not a bad idea to write the tests before the code.

## Checks

There's a script `./lint.sh` at the top directory which will run several
automated checks against the current commit.
You need to make sure your code passes all these checks;
GitHub will run the same tests on any submitted code.

Here are some details about what is checked:

### Style

Your code should conform to the style of the rest of the OTIS,
which follows Google's standards.

- The codebase uses `isort` and `black`
  for linting and formatting of Python files,
  to ensure the uniformity of style across the repository.
- In addition, `djlint` is used to format the HTML templates.

To preserve your sanity you may optionally configure
your editor to automatically apply `black` and `djlint` after each save:
if you're using a sufficiently sophisticated editor,
you can probably configure it to do so.

### Unit testing

Running `python manage.py test` in the top directory will run Django's unit
testing suite. This runs all the checks defined in `**/tests.py`.

The `./lint.sh` will actually run `coverage run manage.py test` so it can then
generate a [coverage report](https://coverage.readthedocs.io/en/6.4.4/) showing
which lines of code were actually checked at some point by at least one unit
test. The resulting percentage is a barometer on how far behind Evan is on
writing tests for some of the older code.

### Type checking

If you're new to development, skip this section.
I'll talk to you more about it later.

The OTIS-WEB repository is heavily type-checked.
We use `pyflakes` and `pyright` are to catch type errors and other
issues. This means type annotations are usually required for function
parameters or when initializing empty lists or dictionaries.

You should be able to use `pyflakes` in pure Python.
To use `pyright`, you'll need to do a separate installation process:
follow [the README](https://github.com/Microsoft/pyright#installation).

If your editor supports language server protocols,
you should be able to catch these errors inline.
If your editor doesn't, consider switching ;)

## Submitting

Once you have a first draft ready for Evan to look at,
you should submit a pull request!

If you followed the instructions earlier,
you should have your own fork of OTIS-WEB.
Commit your changes to this fork,
and then [submit a pull request](https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).

When you submit a pull request,
GitHub will automatically run several checks on the code;
they are roughly the same checks described above,
and the exact specification can be read in `.github/workflows/main.yml`
If this is your first time doing this sort of thing
(and you didn't run `./lint.sh` successfully)
it's likely that at least one of these checks will fail.
Don't freak out; I'll help you through getting the tests to pass.

## For people with some software experience

### Pre-commit hooks

A mentioned above, the script `./lint.sh` will run all tests.
So you might like to do something like

```bash
echo "./lint.sh" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

which will prevent you from pushing a commit
that isn't going to pass the tests on GitHub.

### Docker

If you're using Docker, @AmoleR has created Dockerfile.dev that works well enough.
Something to note is that the last line (creation of `superuser`) doesn't actually
work right now due to the interactive nature of django's default, so you have to
manually run it. To spin up the image, run

```sh
docker build -f Dockerfile.dev -t otis-web .
docker run \
  -v $(pwd):/app \ # This links your current edits into the docker
  -p 8000:8000   \ # This maps ports. Change the first number if you wish.
  -it            \ # Connect terminal stdin/stdout with docker
  otis-web sh
```

Once in there, use `poetry run python ...` to run any python scripts. Also make sure
that you start the runserver with `poetry run python manage.py runserver 0.0.0.0:8000`,
as this will connect to the port you put in the `docker run` command. If you changed
it from port 8000 in the `docker run` command, **DO NOT** change it here - instead, just
go to `localhost:PORT`, where `PORT` is the specified port (not 8000 if you changed it).
