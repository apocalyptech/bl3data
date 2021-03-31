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
import lzma

# Used for testing if I'd figured out the translation from pakfile paths
# to object paths, by looping through my generated contents-* files and
# comparing against my already-sorted BL3 extraction dir.  Not really of
# much use anymore, but I'm a digital packrate, so here it is anyway.

# Parsing the contents files
mount_re = re.compile('^Mounted at: (?P<mountpoint>.*)\s*$')
item_re = re.compile('^ - (?P<objectname>.*\.(uasset|umap))\s*$')

# Parsing the object paths themselves
plugins_re = re.compile('^(?P<firstpart>\w+)/Plugins/(?P<lastpart>.*)\s*$')
content_re = re.compile('^(?P<junk>.*/)?(?P<firstpart>\w+)/Content/(?P<lastpart>.*)\s*$')

# Extracted dir; walking this ahead of time so that we can match
# case-insensitively laster
all_files = set()
extract_dir = '/usr/local/games/bl3_decrypt/extracted'
trim = len(extract_dir)+1
for dirpath, _, filenames in os.walk(extract_dir):
    dirpath = dirpath[trim:]
    for filename in filenames:
        all_files.add(f'{dirpath}/{filename}'.lower())

# Now loop
cur_mount = None
for filename in sorted(os.listdir('.')):
    if filename.startswith('contents-') and filename.endswith('.txt.xz'):
        with lzma.open(filename, 'rt', encoding='latin1') as df:
            for line in df:

                if match := mount_re.match(line):
                    # Found a new mountpoint
                    cur_mount = match.group('mountpoint')
                    if cur_mount.startswith('../../../'):
                        cur_mount = cur_mount[9:]
                    elif cur_mount == '/':
                        # This only shows up in "empty" pakfiles, so whatever
                        cur_mount = ''

                elif match := item_re.match(line):
                    # Found a line
                    objectname = match.group('objectname')
                    assert(cur_mount is not None)
                    objectname_full = f'{cur_mount}{objectname}'

                    # If we're a plugin, strip out the plugin bit first
                    if match2 := plugins_re.match(objectname_full):
                        objectname_full = match2.group('lastpart')

                    # If we're a "content", strip that out next
                    if match2 := content_re.match(objectname_full):
                        firstpart = match2.group('firstpart')
                        lastpart = match2.group('lastpart')
                        junk = match2.group('junk')
                        #if junk and junk != '':
                        #    print('{}, {}, {}'.format(junk, firstpart, lastpart))
                        if firstpart == 'OakGame':
                            firstpart = 'Game'
                        elif firstpart == 'Wwise':
                            firstpart = 'WwiseEditor'
                        objectname_full = '{}/{}'.format(
                                firstpart,
                                lastpart,
                                )

                    # Now check to see if we've been found
                    obj_to_check = objectname_full.lower()
                    if obj_to_check not in all_files:
                        raise Exception('{} -> {} not found!'.format(
                            match.group('objectname'),
                            objectname_full,
                            ))


