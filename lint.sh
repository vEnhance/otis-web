#!/bin/sh

echo "Generating requirements.txt ..."
echo "---------------------------"
poetry export > requirements.txt
echo ""

echo "Making migrations ..."
echo "---------------------------"
python manage.py makemigrations
python manage.py migrate
echo ""

echo "Tidying files with yapf ..."
echo "---------------------------"
yapf --in-place */*.py */templatetags/*.py */management/commands/*.py
echo ""

echo "Running manage.py check ..."
echo "---------------------------"
if ! python manage.py check; then
	echo "FAILED: python manage.py check failed" >> /dev/stderr
	exit 1
fi
echo ""

echo "Running pyright ..."
echo "---------------------------"
if ! pyright; then
	echo "FAILED: pyright failed" >> /dev/stderr
	exit 1
fi
echo ""

echo "Running pyflake ..."
echo "---------------------------"
if ! pyflakes */*.py */templatetags/*.py */management/commands/*.py; then
	echo "FAILED: pyflakes gave nonzero status"
	exit 1
fi
echo ""

echo "Running coverage/tests ..."
echo "---------------------------"
if ! coverage run manage.py test; then
	echo "FAILED: tests failed"
	exit 1
fi
echo ""

echo "Generating coverage report ..."
coverage report --skip-empty --skip-covered
