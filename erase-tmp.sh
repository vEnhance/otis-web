#!/bin/bash

rm -f media/badges/UNIT_TESTING_*.png
rm -f media/psets/*/*/UNIT_TESTING_pset*.txt
rm -f media/global/*/UNIT_TESTING_announcement*.txt

find media/psets/ -type d -empty -delete
find media/global/ -type d -empty -delete
