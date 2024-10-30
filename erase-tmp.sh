#!/usr/bin/env bash
set -euxo pipefail

find media/ -type f -name "TESTING_*.*" -delete
find media/ -type f -name "content?.txt" -delete
find media/ -type f -name "content.txt" -delete
find media/ -type f -name "new_content.txt" -delete
find media/agreement -type f -name "user_*.pdf" -delete
find media/psets/ -type d -empty -delete
find media/scripts/ -type d -empty -delete
find media/global/ -type d -empty -delete
