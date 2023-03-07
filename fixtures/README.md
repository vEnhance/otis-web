This folder contains a bunch of test data used to make local instances easier to
work with.

## tl;dr

If you want things to "just work", probably just

`python manage.py loaddata fixtures/all.json`

and you'll have a reasonably healthy database of stuff that you can use.

## Generator script

If you have an empty database, you can run

`./fixtures/gen-dummy-data.sh`

and it'll generate some dummy data dynamically to play with.
Note that this takes multiple minutes on my machine,
for reasons I can't figure out.

In fact, `fixtures/all.json` is just a snapshot of one run of this script.
That's probably just easier.

## Disclaimer

None of the data here is a puzzle or diamond.

Also, everything in this folder is a total mess.
Pull requests to make this less of a pile of sludge are most welcome.