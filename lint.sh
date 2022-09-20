#!/bin/bash

# Pro-tip:
# echo "./lint.sh" > .git/hooks/pre-commit
# chmod +x .git/hooks/pre-commit

FAILED_HEADER="\033[1;31mFAILED:\033[0m"
BAD_FILE="/tmp/${PWD##*/}.bad"
GOOD_FILE="/tmp/${PWD##*/}.good"

TO_CHECK=$(git ls-files '*.py' | grep -v migrations/ | grep -v /apps.py)
COMMIT_ID=$(git rev-parse HEAD)

if [ -f $GOOD_FILE ]; then
	if [ "$COMMIT_ID" == "$(cat $GOOD_FILE)" ]; then
		echo -e "-----------------------------------------------------------------------"
		echo -e "\033[1;32m$COMMIT_ID\033[0m was marked all-OK, exiting..."
		echo -e "-----------------------------------------------------------------------"
		exit 0
	fi
fi

if [ -f $BAD_FILE ]; then
	if [ "$COMMIT_ID" == "$(cat $BAD_FILE)" ]; then
		echo -e "-----------------------------------------------------------------------"
		echo -e "\033[1;33m$COMMIT_ID\033[0m was marked faulty, aborting..."
		echo -e "-----------------------------------------------------------------------"
		exit 1
	fi
fi

if [ "$1" == "--force" ]; then
	echo -e "\033[1;31m]$COMMIT_ID\033[0m not being compared to upstream"
	echo -e "---------------------------"
	echo -e ""
else
	echo -e "\033[1;35mChecking against upstream ...\033[0m"
	echo -e "---------------------------"
	git fetch
	if [ "$(git rev-list --count HEAD..@\{u\})" -gt 0 ]; then
		echo -e "$FAILED_HEADER Upstream is ahead of you"
		echo $COMMIT_ID > $BAD_FILE
		exit 1
	fi
	echo -e ""
fi

echo -e "\033[1;35mRunning pyflakes ...\033[0m"
echo -e "---------------------------"
if ! pyflakes .; then
	echo -e "$FAILED_HEADER pyflakes gave nonzero status"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mMaking migrations ...\033[0m"
echo -e "---------------------------"
if ! python manage.py makemigrations | grep "No changes detected"; then
	echo -e "$FAILED_HEADER I think you forgot a migration!"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
python manage.py migrate
echo -e ""

echo -e "\033[1;35mLinting files with yapf ...\033[0m"
echo -e "---------------------------"
if ! yapf -d $TO_CHECK; then
	echo -e "$FAILED_HEADER Some files that needed in-place edits, editing now..."
	yapf --in-place $TO_CHECK
	echo -e "Better check your work!"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning manage.py check ...\033[0m"
echo -e "---------------------------"
if ! python manage.py check; then
	echo -e "$FAILED_HEADER python manage.py check failed"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning mypy ...\033[0m"
echo -e "---------------------------"
if ! mypy --ignore-missing-imports $TO_CHECK; then
	echo -e "$FAILED_HEADER mypy failed"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning pyright ...\033[0m"
echo -e "---------------------------"
if ! pyright; then
	echo -e "$FAILED_HEADER pyright failed"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "\033[1;35mRunning coverage/tests ...\033[0m"
echo -e "---------------------------"
if ! coverage run manage.py test --shuffle 1337; then
	echo -e "$FAILED_HEADER Unit tests did not check out"
	echo $COMMIT_ID > $BAD_FILE
	exit 1
fi
echo -e ""

echo -e "Generating coverage report ..."
coverage report -m --skip-empty --skip-covered
coverage html --skip-empty --skip-covered

echo -e "\033[1;32mAll checks passed\033[0m, saving this as a good commit"
echo $COMMIT_ID > $GOOD_FILE
exit 0
