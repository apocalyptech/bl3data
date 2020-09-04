#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Borderlands 3 Data Processing Scripts
# Copyright (C) 2020 CJ Kucera
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

# Tool to make an index of what files exist inside which pakfiles.

import os
import re
import lzma
import paksort
import argparse
import subprocess

mount_re = re.compile(r'Display: Mount point (.*)$')
file_re = re.compile(r'Display: "(.*)" offset')

parser = argparse.ArgumentParser('Output contents of pakfile')
parser.add_argument('pakdir', nargs=1)
args = parser.parse_args()

dir_to_process = args.pakdir[0]
os.environ['WINEPREFIX'] = '/usr/local/winex/testing'
out_file = 'contents-{}.txt.xz'.format(dir_to_process)

# Get the list of pakfiles
pakfiles = []
for filename in os.listdir(dir_to_process):
    if filename.endswith('.pak'):
        pakfiles.append(paksort.PakFile(filename))

# Process
with lzma.open(out_file, 'wt', encoding='utf-8') as df:
    for pakfile in sorted(pakfiles):
        print('Processing {}...'.format(pakfile.filename))

        # Get the contents
        cp = subprocess.run(['wine64', 'UnrealPak.exe', os.path.join(dir_to_process, pakfile.filename), '-list', '-cryptokeys=crypto.json'],
                capture_output=True,
                encoding='utf-8')
        mount_point = None
        contents = []
        wem_bnk_count = 0
        for line in cp.stdout.split("\n"):
            if (match := mount_re.search(line)):
                mount_point = match.group(1)
            elif (match := file_re.search(line)):
                if match.group(1).endswith('.wem') or match.group(1).endswith('.bnk'):
                    wem_bnk_count += 1
                else:
                    contents.append(match.group(1))

        # I don't actually care about .wem/.bnk, which otherwise generates a ton of output.  Ignoring 'em.
        if wem_bnk_count > 0:
            if wem_bnk_count > 1:
                plural = 's'
            else:
                plural = ''
            contents.append('(+ {} .wem/.bnk file{})'.format(wem_bnk_count, plural))

        # Output the contents
        print(pakfile.filename, file=df)
        print('-'*len(pakfile.filename), file=df)
        print('', file=df)
        print('Mounted at: {}'.format(mount_point), file=df)
        print('', file=df)
        print('Contents:', file=df)
        print('', file=df)
        for content in sorted(contents, key=str.casefold):
            print(' - {}'.format(content), file=df)
        print('', file=df)

print('Done!')
