#!/usr/bin/env pypy3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Borderlands 3 Data Unpacking Script
# Copyright (C) 2020 apple1417 + apocalyptech
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND  # noqa: E501
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE1417 OR APOCALYPTECH BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import re
import io
import sys
import struct
import argparse

# unpack_bl3.py used to use the `get_symbols()` function that's now in here,
# looking for a "fuzzy" match between the symbols/names found in the .umap/.uasset
# files and their current disk positions, and the just-extracted "raw" file
# locations.  This was done so that objects could get moved over to the same
# filesystem location that they show up as in-game, for ease of modding, etc.
#
# Anyway, unpack_bl3.py *now* just uses the data given by unrealpak.py itself
# to determine where the files should go, which is nice because it lets us do
# that for non-UE-object files as well, but it turns out that doing so leaves us
# open to some case-sensitivity issues when running all this on Linux (specifically
# with my bl3data library).  This utility loops through an extract dir and
# does the in-object lookups that unpack_bl3.py used to do, though it can go about
# it in a more straightforward way, since the only differences are going to be
# the case in the files/dirs.
#
# This does *not* actually do any moves/renames itself.  Its main purpose is just
# to generate a list of hardcoded fixes which should then be put into unpack_bl3.py,
# so that the extraction process Does The Right Thing in the first place.

def get_symbols(full_path):
    """
    Given a filename, extract UE symbols from it.  This is very hand-wavey and
    probably skips over a bunch of string fields which just happen to be
    zero-length in all BL3 `.uasset` files.  It may fail on non-BL3 pakfiles
    (or even future BL3 pakfiles, depending on how they get exported).
    Returns a dictonary mapping each symbol in lowercase to it's actual
    capitalization.  This allows for easy case-insensitive compares.
    """
    syms = {}
    with open(full_path, 'rb') as datafile:

        def read_int():
            return struct.unpack('<i', datafile.read(4))[0]

        def read_str():
            strlen = read_int()
            if strlen < 0:
                strlen = abs(strlen)
                return datafile.read(strlen * 2)[:-2].decode('utf_16_le')
            else:
                return datafile.read(strlen)[:-1].decode('latin1')

        datafile.seek(28)
        read_str()
        datafile.seek(80, io.SEEK_CUR)
        num_symbols = read_int()
        datafile.seek(72, io.SEEK_CUR)
        for _ in range(num_symbols):
            sym = read_str()
            syms[sym.lower()] = sym
            read_int()

    return syms


parser = argparse.ArgumentParser(
        description='Check BL3 Datafiles for proper case in filenames',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

parser.add_argument('extractdir',
        nargs='?',
        default='extracted_new',
        help='Directory containing data to check',
        )

args = parser.parse_args()

if args.extractdir.endswith('/'):
    args.extractdir = args.extractdir[:-1]
extractdir_len = len(args.extractdir)

re_num_suffix = re.compile(r"^(?P<prefix>.*)_(?P<suffix>\d+)$")

file_moves = set([])
dir_moves = set([])
for dirpath, _, filenames in os.walk(args.extractdir):
    for filename in filenames:
        if filename.endswith('.umap') or filename.endswith('.uasset'):
            full_filename = os.path.join(dirpath, filename)
            cur_path = full_filename[extractdir_len:].rsplit('.', 1)[0]

            # See if we've got a number suffix
            cur_path_prefix = None
            num_suffix = None
            match = re_num_suffix.match(cur_path)
            if match:
                cur_path_prefix = match.group('prefix')
                num_suffix = match.group('suffix')

            # Store lowercase versions
            cur_path_lower = cur_path.lower()
            cur_path_prefix_lower = None
            if cur_path_prefix:
                cur_path_prefix_lower = cur_path_prefix.lower()

            # Get symbols and check stuff
            syms = get_symbols(full_filename)
            found_name = None
            matched_prefix = False
            matched_on = None
            if cur_path_lower in syms:
                found_name = syms[cur_path_lower]
                matched_on = cur_path
            elif cur_path_prefix_lower and cur_path_prefix_lower in syms:
                found_name = syms[cur_path_prefix_lower]
                matched_on = cur_path_prefix
                matched_prefix = True

            # If we didn't find *any* match, abort!
            if not found_name:
                raise Exception('Could not find: {}'.format(cur_path))

            # Now check to see if the case matches or not
            if matched_on != found_name:
                parts_cur = matched_on.split('/')[1:]
                parts_found = found_name.split('/')[1:]
                if parts_cur[-1] != parts_found[-1]:
                    if matched_prefix:
                        file_moves.add(('/'.join(parts_cur[:-1]), parts_cur[-1], '{}_{}'.format(parts_found[-1], num_suffix)))
                    else:
                        file_moves.add(('/'.join(parts_cur[:-1]), parts_cur[-1], parts_found[-1]))

                # TODO: we're "stopping" at the first hit here, so if there are mismatches
                # *below* the one detected here,  you'd have to run this more than once to
                # catch them all.  Of course, depending on the objects that are found, you
                # might end up getting something further down the list anyway, which could
                # result in undefined behavior.  c'est la vie
                for idx in range(len(parts_cur)-2, -1, -1):
                    if parts_cur[idx] != parts_found[idx]:
                        dir_moves.add(('/'.join(parts_cur[:idx+1]), '/'.join(parts_found[:idx+1])))
                        break

if len(file_moves) > 0:
    print('File Moves:')
    for dirname, file_from, file_to in file_moves:
        print(' - In {}: {}.* -> {}.*'.format(dirname, file_from, file_to))
    print('')

if len(dir_moves) > 0:
    print('Dir Moves:')
    for dir_from, dir_to in dir_moves:
        print(' - {}/ -> {}/'.format(dir_from, dir_to))
    print('')

if len(file_moves) == 0 and len(dir_moves) == 0:
    print('No changes required!')

