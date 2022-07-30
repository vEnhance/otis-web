#!/bin/bash

# Pro-tip:
# echo "./lint.sh" > .git/hooks/pre-commit
# chmod +x .git/hooks/pre-commit

FAILED_HEADER="\033[1;31mFAILED:\033[0m"
BAD_FILE=/tmp/otisweb.bad
GOOD_FILE=/tmp/otisweb.good


if [ -f $GOOD_FILE ]; then
	if [ "$(git rev-parse HEAD)" == "$(cat $GOOD_FILE)" ]; then
		echo -e "-----------------------------------------------------------------------"
		echo -e "\033[1;32m$(git rev-parse HEAD)\033[0m was marked all-OK, exiting..."
		echo -e "-----------------------------------------------------------------------"
		exit 0
	fi
fi

if [ -f $BAD_FILE ]; then
	if [ "$(git rev-parse HEAD)" == "$(cat $BAD_FILE)" ]; then
		echo -e "-----------------------------------------------------------------------"
		echo -e "\033[1;33m$(git rev-parse HEAD)\033[0m was marked faulty, aborting..."
		echo -e "-----------------------------------------------------------------------"
		exit 1
	fi
fi

echo -e "\033[1;35mChecking against upstream ...\033[0m"
echo -e "---------------------------"
git fetch
if [ "$(git rev-list --count HEAD..@\{u\})" -gt 0 ]; then
	echo -e "$FAILED_HEADER Upstream is ahead of you"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning pyflakes ...\033[0m"
echo -e "---------------------------"
if ! pyflakes .; then
	echo -e "$FAILED_HEADER pyflakes gave nonzero status"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mGenerating requirements.txt ...\033[0m"
echo -e "---------------------------"
poetry export -E production > requirements.txt
if ! git diff --exit-code requirements.txt; then
	echo -e "$FAILED_HEADER You need to commit requirements.txt"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mMaking migrations ...\033[0m"
echo -e "---------------------------"
if ! python manage.py makemigrations | grep "No changes detected"; then
	echo -e "$FAILED_HEADER I think you forgot a migration!"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
python manage.py migrate
echo -e ""

echo -e "\033[1;35mLinting files with yapf ...\033[0m"
echo -e "---------------------------"
if ! yapf -d $(git ls-files **.py | grep -v migrations); then
	echo -e "$FAILED_HEADER Some files that needed in-place edits, editing now..."
	yapf --in-place $(git ls-files **.py | grep -v migrations)
	echo -e "Better check your work!"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning manage.py check ...\033[0m"
echo -e "---------------------------"
if ! python manage.py check; then
	echo -e "$FAILED_HEADER python manage.py check failed"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning pyright ...\033[0m"
echo -e "---------------------------"
if ! pyright; then
	echo -e "$FAILED_HEADER pyright failed"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning coverage/tests ...\033[0m"
echo -e "---------------------------"
if ! coverage run manage.py test; then
	echo -e "$FAILED_HEADER Unit tests did not check out"
	git rev-parse HEAD > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "Generating coverage report ..."
coverage report --skip-empty --skip-covered

echo -e "\033[1;32mAll checks passed\033[0m, saving this as a good commit"
git rev-parse HEAD > $GOOD_FILE
