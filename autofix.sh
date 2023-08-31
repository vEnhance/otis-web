#!/bin/bash

# This auto-fixes style issues that can be resolved automatically

readarray -t PY_FILES_ARRAY < <(git ls-files '*.py')
readarray -t HTML_FILES_ARRAY < <(git ls-files '**/templates/**.html')
readarray -t PRETTIER_FILES_ARRAY < <(git ls-files '*.css' '*.js' '*.md' '*.ts')
readarray -t PRETTIER_FILES_ARRAY < <(find "${PRETTIER_FILES_ARRAY[@]}" -not -type l)

echo -e "\033[1;35mRunning isort ...\033[0m"
isort --quiet --profile black "${PY_FILES_ARRAY[@]}"

echo -e "\033[1;35mRunning black ...\033[0m"
black "${PY_FILES_ARRAY[@]}"

echo -e "\033[1;35mRunning djlint ...\033[0m"
djlint --reformat --quiet "${HTML_FILES_ARRAY[@]}"

echo -e "\033[1;35mRunning prettier ...\033[0m"
prettier --write "${PRETTIER_FILES_ARRAY[@]}"

exit 0
