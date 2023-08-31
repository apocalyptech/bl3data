#!/bin/bash
# vim: set expandtab tabstop=4 shiftwidth=4:

read -sp 'Enter bl3pakfile pass: ' PASS
echo
echo "SQLite dump/conversion..."
echo
rm bl3pakfile.sqlite3*
/usr/local/dv/virtualenv/mysql2sqlite/bin/mysql2sqlite -f bl3pakfile.sqlite3 -d bl3pakfile -u bl3pakfile -h mcp -V --mysql-password ${PASS} && zip bl3pakfile.sqlite3.zip bl3pakfile.sqlite3 && rm bl3pakfile.sqlite3 && ls -lh bl3pakfile.sqlite3*
