#!/bin/bash

git rev-parse HEAD > /tmp/otisweb.good

echo -e "-----------------------------------------------------------------------"
echo -e "\033[1;31m$(git rev-parse HEAD)\033[0m had lint.sh bypassed"
echo -e "-----------------------------------------------------------------------"

