#!/bin/bash
# vim: set expandtab tabstop=4 shiftwidth=4:

#WINEPREFIX="/usr/local/winex/lutris/runners/wine/ge-protonified-4.10-x86_64"
#PATH="${WINEPREFIX}/bin:${PATH}"
export WINEPREFIX="/usr/local/winex/testing"

if [ "x$1" == "x" ]
then
    echo "Need a directory from which we'll read pak files"
    exit
fi

echo "Processing $1..."
cd $1
for file in *.pak
do
    wine64 ../UnrealPak.exe $file -extract extractednew -cryptokeys=crypto.json
done
cd ..

