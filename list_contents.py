#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Borderlands 3 Data Processing Scripts
# Copyright (C) 2020-2021 CJ Kucera
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
#
# See `web-pakfile-lookup/bl3pakfile.schema.sql` for the MySQL/MariaDB database
# schema used by the database-integration bits of this.

import os
import re
import sys
import lzma
import paksort
import argparse
import subprocess

# Args
parser = argparse.ArgumentParser(
        description='Output contents of pakfile to a contents file',
        epilog="""
            Given a patch dir containing pakfiles, writes out the file
            contents-<dirname>.txt.xz.  That file will describe the
            contents of all the pakfiles found in that dir, skipping over
            .wem/.bnk files (since I don't personally care about those).
            If the --database flag is specified, this util will insert
            full information about the patch to the database.  Setting
            this up is left as an excercise for the reader.
        """
        )

parser.add_argument('-d', '--database',
        action='store_true',
        help='Also import pakfile contents to pakfile database (mostly just useful for Apocalyptech)',
        )

parser.add_argument('pakdir',
        nargs=1,
        help='Patch dir (containing paks) to process')

args = parser.parse_args()

# Classes that will be used for the database integration stuff.  These
# won't really be used for anything if you're just generating textfiles.

class Patch:

    def __init__(self, pid, dirname, released, description):
        self.pid = pid
        self.dirname = dirname
        self.released = released
        self.description = description

    @staticmethod
    def from_db(row):
        return Patch(row['pid'],
                row['dirname'],
                row['released'],
                row['description'])

    def __str__(self):
        return self.dirname

    def __repr__(self):
        return f'Patch<{self.dirname}>'

class Pakfile:

    def __init__(self, fid, patch, filename, mountpoint, ordernum):
        self.fid = fid
        self.patch = patch
        self.filename = filename
        self.mountpoint = mountpoint
        self.ordernum = ordernum

    @staticmethod
    def from_db(row, patches_by_id):
        return Pakfile(fid=row['fid'],
                patch=patches_by_id[row['pid']],
                filename=row['filename'],
                mountpoint=row['mountpoint'],
                ordernum=row['ordernum'])

    def __str__(self):
        return self.filename

    def __repr__(self):
        return f'Pakfile<{self.filename}>'

class GameObject:

    def __init__(self, oid, filename_full, filename_base=None):
        self.oid = oid
        self.filename_full = filename_full
        if filename_base:
            self.filename_base = filename_base
        else:
            self.filename_base = filename_full.split('/')[-1].rsplit('.', 1)[0]
        self.pakfiles = set()

    @staticmethod
    def from_db(row):
        return GameObject(oid=row['oid'],
                filename_full=row['filename_full'],
                filename_base=row['filename_base'])

    def __str__(self):
        return self.filename_full

    def __repr__(self):
        return f'GameObject<{self.filename_full}>'

# Extra imports if we're doing database stuff (also connect to the DB)
if args.database:
    import appdirs
    import MySQLdb
    import configparser
    import MySQLdb.cursors

    # Lookup objects we'll use.
    patches = {}
    patches_by_id = {}
    pakfiles = {}
    pakfiles_by_id = {}
    objects = {}
    objects_by_id = {}

    # Read in databae params
    config_dir = appdirs.user_config_dir('bl3pakfile')
    config_file = os.path.join(config_dir, 'bl3pakfile.ini')
    config = configparser.ConfigParser()
    config.read(config_file)

    # Connect to the DB
    db = MySQLdb.connect(
            user=config['mysql']['user'],
            passwd=config['mysql']['passwd'],
            host=config['mysql']['host'],
            db=config['mysql']['db'],
            cursorclass=MySQLdb.cursors.DictCursor)
    curs = db.cursor()

    # Read in known patches
    curs.execute('select * from patch')
    for row in curs:
        patch = Patch.from_db(row)
        assert(patch.dirname not in patches)
        patches[patch.dirname] = patch
        patches_by_id[patch.pid] = patch

    # Read in known pakfiles
    curs.execute('select * from pakfile')
    for row in curs:
        pakfile = Pakfile.from_db(row, patches_by_id)
        assert(pakfile.filename not in pakfiles)
        pakfiles[pakfile.filename] = pakfile
        pakfiles_by_id[pakfile.fid] = pakfile

    # Read in known objects
    curs.execute('select * from object')
    for row in curs:
        gameobject = GameObject.from_db(row)
        assert(gameobject.filename_full not in objects)
        objects[gameobject.filename_full.lower()] = gameobject
        objects_by_id[gameobject.oid] = gameobject

    # Read in known object-to-pakfile mappings
    curs.execute('select * from o2f')
    for row in curs:
        gameobject = objects_by_id[row['oid']]
        gameobject.pakfiles.add(row['fid'])

# Some regular expressions we'll use to parse
mount_re = re.compile(r'Display: Mount point (.*)$')
file_re = re.compile(r'Display: "(.*)" offset')
patchdate_re = re.compile(r'^pak-(\d{4}-\d{2}-\d{2})-.*$')

# Some other vars
dir_to_process = args.pakdir[0]
os.environ['WINEPREFIX'] = '/usr/local/winex/testing'
out_file = 'contents-{}.txt.xz'.format(dir_to_process)

# Insert into DB, if we need to
if args.database:
    desc_filename = os.path.join(dir_to_process, 'description.txt')
    description = None
    with open(desc_filename) as df:
        description = df.read().strip()
    assert(description is not None)
    if dir_to_process in patches:
        patch = patches[dir_to_process]
        if patch.description != description:
            print(f'Updating {dir_to_process} description in DB...')
            curs.execute('update patch set description=%s where pid=%s', (
                description,
                patch.pid,
                ))
            db.commit()
    else:
        match = patchdate_re.match(dir_to_process)
        assert(match)
        print(f'Adding patch {dir_to_process} to DB...')
        curs.execute('insert into patch (dirname, released, description) values (%s, %s, %s)', (
            dir_to_process,
            match.group(1),
            description
            ))
        new_id = curs.lastrowid
        db.commit()
        # This select redirect is stupid, but there's so few patches is hardly matters.
        curs.execute('select * from patch where pid=%s', (new_id,))
        patch = Patch.from_db(curs.fetchone())
        assert(patch.dirname not in patches)
        patches[patch.dirname] = patch
        patches_by_id[patch.pid] = patch

# Get the list of pakfiles
pakfiles_fs = []
for filename in os.listdir(dir_to_process):
    if filename.endswith('.pak'):
        new_pakfile = paksort.PakFile(filename)
        pakfiles_fs.append(new_pakfile)

# Regexes to help convert an in-pak pathname to an in-game object path
plugins_re = re.compile(r'^(?P<firstpart>\w+)/Plugins/(?P<lastpart>.*)\s*$')
content_re = re.compile(r'^(?P<junk>.*/)?(?P<firstpart>\w+)/Content/(?P<lastpart>.*)\s*$')

# Process
with lzma.open(out_file, 'wt', encoding='utf-8') as df:
    for pakfile in sorted(pakfiles_fs):
        print('Processing {}...'.format(pakfile.filename))

        # Get the contents
        cp = subprocess.run(['wine64', 'UnrealPak.exe', os.path.join(dir_to_process, pakfile.filename), '-list', '-cryptokeys=crypto.json'],
                capture_output=True,
                encoding='utf-8')
        mount_point = None
        contents = []
        wem_bnk_count = 0
        db_changed = False
        db_pakfile = None
        for line in cp.stdout.split("\n"):
            if (match := mount_re.search(line)):
                mount_point = match.group(1)

                # Make sure our database is up to date, if we've been told to
                if args.database:

                    if pakfile.filename in pakfiles:

                        # Update our mount point if it happens to be different
                        db_pakfile = pakfiles[pakfile.filename]
                        if db_pakfile.mountpoint != mount_point:
                            print(f'Updating {db_pakfile.filename} mountpoint in DB...')
                            curs.execute('update pakfile set mountpoint=%s where fid=%s', (
                                mount_point,
                                db_pakfile.fid,
                                ))
                            db_changed = True
                            db_pakfile.mountpoint = mount_point

                    else:

                        # Add to the database
                        print(f'Adding pakfile {pakfile.filename} to DB...')
                        curs.execute('insert into pakfile (pid, filename, mountpoint, ordernum) values (%s, %s, %s, %s)', (
                            patches[dir_to_process].pid,
                            pakfile.filename,
                            mount_point,
                            pakfile.order_num,
                            ))
                        new_id = curs.lastrowid
                        # This select redirect is stupid, but there's so few pakfiles is hardly matters.
                        curs.execute('select * from pakfile where fid=%s', (new_id,))
                        db_pakfile = Pakfile.from_db(curs.fetchone(), patches_by_id)
                        assert(db_pakfile.filename not in pakfiles)
                        pakfiles[db_pakfile.filename] = db_pakfile
                        pakfiles_by_id[db_pakfile.fid] = db_pakfile
                        db_changed = True

                # Massage the mount point for when we figure out the "real" paths, below.
                # (no longer doing this; just gonna do it in code on the web side, to make
                # the DB size smaller - we save ~100MB by omitting it)
                #
                #if mount_point.startswith('../../../'):
                #    mount_point = mount_point[9:]
                #elif mount_point == '/':
                #    # This only shows up in "empty" pakfiles, so whatever
                #    mount_point = ''

            elif (match := file_re.search(line)):
                inner_filename = match.group(1)

                # Add to contents (for the text file output)
                if inner_filename.endswith('.wem') or inner_filename.endswith('.bnk'):
                    wem_bnk_count += 1
                else:
                    contents.append(inner_filename)

                # If we're working with the database, make sure this object is in the DB
                # (and also that its pakfile mapping is in there)
                if args.database:

                    # Not actually processing real-name stuff anymore!  This method works, but I'm
                    # doing it on the display side on the web, instead, to save on database space.
                    #
                    # Routine to get our *real* filename.  I'm quite sure this is correct for "real" game
                    # objects, since I've checked it versus my original extraction/reorganization techniques,
                    # though for non-game-objects I'm not entirely sure if it makes total sense.
                    #real_filename = f'{mount_point}{inner_filename}'

                    # If we're a "plugin" path, strip out the plugin bit.
                    #if match := plugins_re.match(real_filename):
                    #    real_filename = match.group('lastpart')

                    # Now if we're a "Content", strip that out as well (and apply some hardcoded transforms)
                    #if match := content_re.match(real_filename):
                    #    firstpart = match.group('firstpart')
                    #    lastpart = match.group('lastpart')
                    #    if firstpart == 'OakGame':
                    #        firstpart = 'Game'
                    #    elif firstpart == 'Wwise':
                    #        firstpart = 'WwiseEditor'
                    #    real_filename = f'/{firstpart}/{lastpart}'

                    # Get the db object
                    if inner_filename.lower() in objects:
                        db_object = objects[inner_filename.lower()]
                    else:
                        db_object = GameObject(-1, inner_filename)
                        curs.execute('insert into object (filename_base, filename_full) values (%s, %s)', (
                            db_object.filename_base,
                            db_object.filename_full,
                            ))
                        db_object.oid = curs.lastrowid
                        assert(db_object.filename_full.lower() not in objects)
                        objects[db_object.filename_full.lower()] = db_object
                        objects_by_id[db_object.oid] = db_object
                        db_changed = True

                    # Mapping additions
                    if db_pakfile.fid not in db_object.pakfiles:
                        db_object.pakfiles.add(db_pakfile.fid)
                        curs.execute('insert into o2f (oid, fid) values (%s, %s)', (
                            db_object.oid,
                            db_pakfile.fid,
                            ))
                        db_changed = True

        # Commit our DB if files have been added
        if args.database and db_changed:
            db.commit()

        # I don't actually care about .wem/.bnk, which otherwise generates a ton of output.  Ignoring 'em.
        # (though they *do* get added to the database version, since that's intended for more targetted
        # lookups)
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
