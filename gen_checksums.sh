#!/bin/bash
# vim: set expandtab tabstop=4 shiftwidth=4:

CHKSUM="sha256sum"
OUTFILE="checksums-${CHKSUM}.txt"

for dir in $@
do

    echo "Processing ${dir}"

    echo ${dir} >> ${OUTFILE}
    echo >> ${OUTFILE}
    cd ${dir}
    /bin/ls *.pak | ../paksort.py | xargs ${CHKSUM} >> ../${OUTFILE}
    cd ..
    echo >> ${OUTFILE}

done
