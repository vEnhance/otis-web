#!/bin/sh

echo "Tidying files with yapf..."
echo "---------------------------"
yapf --in-place */*.py */tests/*.py */templatetags/*.py */management/commands/*.py

echo "Running manage.py check ..."
echo "---------------------------"
if ! python manage.py check; then
	echo "FAILED: python manage.py check failed" >> /dev/stderr
	exit 1
fi
echo ""

echo "Running pyright type ..."
echo "---------------------------"
if ! pyright; then
	echo "FAILED: python manage.py check failed" >> /dev/stderr
	exit 1
fi

echo "Running pyflake ..."
echo "---------------------------"
if ! pyflakes */*.py */tests/*.py */templatetags/*.py */management/commands/*.py; then
	echo "FAILED: pyflakes gave nonzero status"
	exit 1
fi

echo "Running coverage/tests ..."
echo "---------------------------"
if ! coverage run manage.py test; then
	echo "FAILED: tests failed"
	exit 1
fi

echo "Generating coverage report ..."
coverage report --skip-empty --skip-covered
