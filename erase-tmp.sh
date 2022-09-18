#!/bin/bash

TO_DELETE=$(ls media/badges/TESTING_*.png media/psets/*/*/TESTING_pset*.txt media/global/*/TESTING_announcement*.txt media/pdfs/TESTING_*.{tex,pdf} 2> /dev/null)

if [ $(echo $TO_DELETE | wc --words) = 0 ]; then
	echo "No files to delete"
	exit 1
fi

echo $TO_DELETE | tr ' ' '\n' | head -n 8
echo "..."
echo $TO_DELETE | tr ' ' '\n' | tail -n 8
echo "$(echo $TO_DELETE | wc --words) files to delete"

function yes_or_no {
	while true; do
			read -p "$* [y/n]: " yn
			case $yn in
				[Yy]*) return 0  ;;  
				[Nn]*) echo "Aborted" ; return  1 ;;
			esac
	done
}

yes_or_no "Delete?" && echo "nom nom nom" || exit 1

rm -f $TO_DELETE
find media/psets/ -type d -empty -delete
find media/global/ -type d -empty -delete
