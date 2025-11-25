#!/usr/bin/env bash
set -euo pipefail

# Check current branch is main
current_branch=$(git branch --show-current)
if [[ "$current_branch" != "main" ]]; then
  echo "Error: Current branch is '$current_branch', not 'main'"
  exit 1
fi

# Check production remote exists
if ! git remote get-url production &>/dev/null; then
  echo "Error: Remote 'production' does not exist"
  exit 1
fi

# Check origin/main is in sync with local main
git fetch origin
local_main=$(git rev-parse main)
origin_main=$(git rev-parse origin/main)
if [[ "$local_main" != "$origin_main" ]]; then
  echo "Error: Local main is not in sync with origin/main!"
  echo "Local:  $local_main"
  echo "Origin: $origin_main"
  exit 1
fi

# All checks passed, push to production
git push --no-verify production main
