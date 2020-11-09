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

import os
import sys
import paksort
import argparse
import subprocess

###
### Yet more overengineered nonsense!  First up, control vars
###

# Base dirs to find paks
basedirs = {
        'egs': '/usr/local/winex/lutris_games/epic-games-store/drive_c/Program Files/Epic Games/Borderlands3/OakGame',
        'steam': '/usr/local/games/bl3_steam/games/steamapps/common/Borderlands 3/OakGame',
        }

# Where to find them by DLC
basegame_dir = 'Content/Paks'
dlc_dirs = {
        'Dandelion': 'AdditionalContent/Dandelion/Paks',
        'Hibiscus': 'AdditionalContent/Hibiscus/Paks',
        'Geranium': 'AdditionalContent/Geranium/Paks',
        'Alisma': 'AdditionalContent/Alisma/Paks',
        'Ixora': 'AdditionalContent/Ixora/Paks',
        }

# Checksum information.  Using an external binary here on the assumption that it's
# likely to be faster than doing it in Python, though perhaps the difference would
# be negligible at best.
checksum_util = '/usr/bin/sha256sum'
checksum_template = 'checksums-sha256sum-{}.txt'

###
### Now argument parsing
###

parser = argparse.ArgumentParser(
        description='Symlink BL3 paks into dirs organized by patch',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""Each pakdir should have a file named `filelist.txt` which
        just contains a list of the pakfiles which should be included in
        the symlink list.  The util will remove any existing pak symlinks
        before linking in the new ones.""",
        )

parser.add_argument('-s', '--store',
        type=str,
        choices=basedirs.keys(),
        default='steam',
        help='Store from which to link paks',
        )

parser.add_argument('-c', '--checksum',
        action='store_true',
        help='Also write checksums to {}'.format(checksum_template.format('<store>')),
        )

parser.add_argument('pakdir',
        nargs='+',
        help='Pakfile dirs to process',
        )

args = parser.parse_args()

###
### Now do the work
###

print('Processing symlinks for store: {}'.format(args.store))

for dirname in args.pakdir:

    # Sanitize input
    if dirname[-1] == '/':
        dirname = dirname[:-1]
    if '/' in dirname or not dirname.startswith('pak-'):
        print('{} is not a valid pakdir (must start with `pak-` and not include path components), skipping'.format(dirname))
        continue
    if not os.path.isdir(dirname):
        print('{} is not a directory, skipping'.format(dirname))
        continue

    # Find current symlinks to delete, and a list of paks to link in their place.
    print('Processing {}'.format(dirname))
    found_filelist = False
    abort = False
    found_paks = []
    advertised_paks = {}
    for filename in  os.listdir(dirname):
        full_filename = os.path.join(dirname, filename)
        if filename == 'filelist.txt':
            found_filelist = True
            with open(full_filename) as df:
                for line in df:
                    line = line.strip()
                    if not line.endswith('.pak'):
                        print('  ERROR: Found non-.pak file in filelist.txt, aborting this dir')
                        abort = True
                        break

                    # Make sure the specified pakfile exists
                    extra_path = basegame_dir
                    for check, check_extra_path in dlc_dirs.items():
                        if check in line:
                            extra_path = check_extra_path
                            break
                    pak_full = os.path.join(basedirs[args.store], extra_path, line)
                    if not os.path.exists(pak_full):
                        print('  ERROR: Not found, aborting this dir: {}'.format(pak_full))
                        abort = True
                        break

                    # Store the mapping
                    advertised_paks[pak_full] = line
            if abort:
                break
        elif filename.endswith('.pak'):
            if os.path.islink(full_filename):
                found_paks.append(full_filename)
            else:
                print('  ERROR: Found non-symlink pakfile {}, aborting this dir'.format(full_filename))
                abort = True
                break

    # Some sanity checks
    if abort:
        continue
    if not found_filelist:
        print('  ERROR: Could not find filelist.txt, aborting this dir')
        continue
    if len(advertised_paks) == 0:
        print('  WARNING: no paks found in dir, aborting this dir')
        continue

    # Delete existing pak symlinks
    for pakfile in found_paks:
        os.unlink(pakfile)

    # Now symlink in the new ones
    for full_path, pakfile in advertised_paks.items():
        os.symlink(full_path, os.path.join(dirname, pakfile))

    # Report
    print('  - Cleared {} symlinks and created {} more'.format(
        len(found_paks),
        len(advertised_paks),
        ))

    # Write checksums, if we've been told to
    if args.checksum:
        print('  - Writing checksums...')
        checksum_filename = checksum_template.format(args.store)
        with open(checksum_filename, 'a') as df:
            os.chdir(dirname)
            print(dirname, file=df)
            print('', file=df)
            for pakfile in sorted([paksort.PakFile(f) for f in advertised_paks.values()]):
                print('    + {}'.format(pakfile))
                cp = subprocess.run([checksum_util, pakfile.filename], capture_output=True, encoding='utf-8')
                df.write(cp.stdout)
                if len(cp.stderr) > 0:
                    df.write(cp.stderr)
                if cp.returncode != 0:
                    print('WARNING: "{} {}" left return code {}'.format(checksum_util, pakfile, cp.returncode), file=df)
                    print('    ! WARNING: {} left return code {}'.format(checksum_util, cp.returncode))
            print('', file=df)
            os.chdir('..')

