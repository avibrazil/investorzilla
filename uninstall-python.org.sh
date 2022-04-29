#!/bin/sh

# On macOS, completely uninstall python.org’s Python package

for pkg in `pkgutil --pkgs | grep -i python`; do

	# Determine installation path
	SAVEIFS=IFS
	IFS='
'
	for item in `pkgutil --pkg-info $pkg`; do
# 		echo item: $item
		
		v=`echo $item | sed -e 's|volume: \(.*\)|\1|'`
		[[ "volume: $v" == $item ]] && volume=$v
		unset v
		
		l=`echo $item | sed -e 's|location: \(.*\)|\1|'`
		[[ "location: $l" == $item ]] && location=$l
		unset l
	done
	file_location=${volume}${location}
	
	echo
	echo $pkg
	# Iterate over each file to delete it
	for file in `pkgutil --files $pkg`; do
		rm -rf "$file_location/$file"
# 		echo "$file_location/$file"
	done
	
	IFS=SAVEIFS
	
done

# Remove leftovers
rm -rf /Library/Frameworks/Python.framework/
rm -rf /usr/local/bin/pip3*