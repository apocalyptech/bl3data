#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Borderlands 3 Data Processing Scripts
# Copyright (C) 2021 CJ Kucera
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import re
import sys
import struct
import subprocess

# Script used to generate an initial `wwnames.txt` file to use along with the
# wwiser project, for making sense of audio banks in the Borderlands 3 data.
#
#    https://github.com/bnnm/wwiser
#    https://github.com/bnnm/wwiser-utils
#
# The generated list here, by nature, has an awful lot of cruft in it which
# isn't actually useful.  To re-generate the .txt file during `wwiser.py`:
#
#    wwiser.py -g -sl Init.bnk *.bnk
#
# I was worried that CPython might be annoyingly slow for this, but on my
# system it finishes in ~26secs, compared to ~18 for PyPy3.  So: whatever.

###
### Config vars!
###

# Where to find an OSX binary.  Download it with Legendary (requires owning
# the game on EGS).  The OSX binary is unstripped, so there's a lot of
# potentially-useful plaintext in there.  (I honestly don't know if anything
# in there turns out to be useful, or if it's just data stuff.)
#
#    https://github.com/derrod/legendary
#
#    ./cli.py download Catnip --platform=Mac --prefix=OakGame/Binaries --download-only --disable-patching
osx_binary = '/home/pez/legendary/Borderlands3/OakGame/Binaries/Mac/Borderlands3.app/Contents/MacOS/Borderlands3'

# Data directory to find a fully-extracted BL3 data set
data_dir = 'extracted'

# Hash collisions!  Uncomment the ones you want to prune out.  Organizing these
# by pairs, so that the ones colliding are obvious.
collisions_to_remove = set([

    'AS_P1_Transition',
    #'NPC_Mal_Mech_Mov_Servo_Short',

    #'Crea_PlfrEye_Whoosh',
    'WallL_GEN_VARIABLE',

    'AnimGraphNode_StateResult_443A452B4A3BB356AB2A2DA43AF26D9A',
    #'Imp_Surfaces_Debris_Large',

    'CPUMultiplier',
    #'Emt_Mansion_Water_Lapping_Lake_Calm_Lp_03',

    #'Emt_Prologue_Windmill_Metal_Med_Spin_Lp',
    'LegendPositionv',

    'HeldActorInterfaceE',
    #'Oak_DLC3_VOBD_TownfolkMale3_Pain_Stagger',

    ])

# Filename to write out to
output_filename = 'wwnames-firstpass.txt'

###
### And now the app
###

def read_int(df):
    return struct.unpack('<i', df.read(4))[0]

def read_str(df):
    strlen = read_int(df)
    # The length includes a null byte at the end
    # Also decoding to latin1 may not always be the right thing
    # to do, though so far I've not seen anything other than ASCII
    if strlen < 0:
        strlen = abs(strlen)
        return df.read(strlen*2)[:-2].decode('utf_16_le')
    else:
        return df.read(strlen)[:-1].decode('latin1')

# Our set of potential strings
potential_strings = set()

# Grab strings from the main binary
print(f'Grabbing main binary strings from: {osx_binary}')
start_re = re.compile('^[a-zA-Z0-9][a-zA-Z0-9_]*$')
p = subprocess.run(['/usr/bin/strings',
    # UTF-16 strings don't seem to be especially useful
    #'-e', 'l',
    osx_binary,
    ],
    capture_output=True,
    encoding='utf-8',
    )
for line in p.stdout.splitlines():
    match = start_re.match(line)
    if match:
        potential_strings.add(line)

# Walk the object filesystem
print(f'Walking object filesystem from: {data_dir}')
processed = 0
for dirname, dirnames, filenames in os.walk(data_dir):
    for filename in filenames:
        if filename.endswith('.uasset') or filename.endswith('.umap'):

            # Add in our path components
            # We're doing this because many of the object names show up in there, but
            # with their first underscore-delimited part removed.  This is the case
            # at least for `WE_*` objects and `WwiseBank_*` objects.  This is probably
            # a bit unnecessary now that we're reading in the name catalog from the
            # objects directly -- these names probably show up in there anyway -- but
            # compared reading the data it's super quick to do, so whatever.
            parts = filename.rsplit('.', 1)[0].split('_')
            for i in range(len(parts)):
                potential_strings.add('_'.join(parts[i:]))

            # Add in everything from the object's name index
            with open(os.path.join(dirname, filename), 'rb') as df:

                # Blah, initial header stuff
                df.read(20)

                # Some number of FCustomVersion
                length = read_int(df)
                for _ in range(length):
                    df.read(20)

                total_header_size = read_int(df)
                folder_name = read_str(df)
                # package_flags is actually a uint, but whatever.
                package_flags = read_int(df)
                name_count = read_int(df)
                name_offset = read_int(df)

                # Now we've read enough to skip right to the name catalog
                df.seek(name_offset)
                for _ in range(name_count):
                    name = read_str(df)
                    if '/' not in name:
                        potential_strings.add(name)
                    # This is actually two shorts
                    read_int(df)

            # Report
            processed += 1
            if processed % 1000 == 0:
                print(f' - Processed {processed} files...')

# Process our known collisions
for collision in collisions_to_remove:
    potential_strings.remove(collision)

with open(output_filename, 'w') as df:
    print(f'Writing out to: {output_filename}')
    print('# Borderlands 3', file=df)
    print('', file=df)
    for event in sorted(potential_strings):
        print(event, file=df)

