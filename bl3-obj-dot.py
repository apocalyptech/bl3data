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
import json
import subprocess

# Script to serialize the specified object file using JohnWickParse, generate a
# graphviz-based "dot" file based on the resulting JSON which traces how the
# various exports relate to each other, and then convert that dotfile into an
# output format (currently defaulting to PNG, below -- SVG would be another
# good output type).  Will also display the resulting image if the output type
# is an image.
#
# For the object name, you can leave off the extension entirely (as
# JohnWickParse expects), specify the .uasset or .uexp file (or even the .json
# file if it's already serialized, though this will blindly re-serialize it),
# or you can actually have a bare `.` at the end rather than an extension, as a
# convenience to myself, since tab-completion will generally stop at that point,
# and this way I don't have to expend all the energy required to hit backspace
# once.  My life is a hard one, is what I'm saying.
#
# This expects the JWP serializations to include my custom additions found at
# https://github.com/apocalyptech/JohnWickParse/tree/indexed_arrays

# External commands we call
cmd_serialize = '/home/pez/bin/ueserialize'
cmd_dot = '/usr/bin/dot'
cmd_view = '/usr/bin/feh'

# Type of output.  `cmd_view` will only be called if this is png/jpg/gif
dot_output = 'png'

# Keep track of attribute nodes we've already generated and linked to
linked_history = set()

def link_path(odf, export_idx, path):
    """
    Given a `path`, which is a list of attribute references originating from the given
    `export_idx`, write out appropriate attribute nodes and links to those attribute
    nodes to `odf`.  Uses the global var `linked_history` to keep track of which attribute
    nodes already exist and have been linked-to, so we don't double up on nodes or edges.
    """
    global linked_history
    prev_path = 'export_{}'.format(export_idx)
    for i in range(len(path)):
        path_var = '_'.join(path[:i+1])
        path_var = path_var.replace('[', '')
        path_var = path_var.replace(']', '')
        path_var = 'export_{}_{}'.format(export_idx, path_var)
        if path_var not in linked_history:
            print('{} [label=<{}> shape=ellipse style=filled fillcolor=gold1];'.format(
                path_var,
                path[i],
                ), file=odf)
            print('{} -> {};'.format(prev_path, path_var), file=odf)
            linked_history.add(path_var)
        prev_path = path_var
    return prev_path

def process_dict(odf, export_idx, data, cur_path):
    """
    Processes the given dict `data` (extracted from inside an object JSON), originating
    from inside the export `export_idx`, and create links between exports where
    appropriate.  Writes to `odf`.  `cur_path` is a list of attribute references
    originating from the given export.
    """
    # If we're an export, generate a link
    if 'export' in data:
        if data['export'] != 0:
            from_path = link_path(odf, export_idx, cur_path)
            print('{} -> {};'.format(from_path, 'export_{}'.format(data['export'])), file=odf)
    else:
        for k, v in data.items():
            if type(v) == dict:
                process_dict(odf, export_idx, v, list(cur_path) + [k])
            elif type(v) == list:
                process_list(odf, export_idx, v, list(cur_path) + [k])
            elif type(v) == str or type(v) == int or type(v) == float or type(v) == bool:
                pass
            else:
                print('Unknown value type for {} {}: {}'.format(cur_path, k, type(v)))

def process_list(odf, export_idx, data, cur_path):
    """
    Processes the given list `data` (extracted from inside an object JSON), originating
    from inside the export `export_idx`, and create links between exports where
    appropriate.  Writes to `odf`.  `cur_path` is a list of attribute references
    originating from the given export.
    """
    for idx, v in enumerate(data):
        if type(v) == dict:
            process_dict(odf, export_idx, v, list(cur_path) + ['[{}]'.format(idx)])
        elif type(v) == list:
            process_list(odf, export_idx, v, list(cur_path) + ['[{}]'.format(idx)])
        elif type(v) == str or type(v) == int or type(v) == float or type(v) == bool:
            pass
        else:
            print('Unknown value type for {} [{}]: {}'.format(cur_path, idx, type(v)))

# Grab the filename to process
filename = sys.argv[1]
if filename.endswith('.'):
    filename = filename[:-1]
if '.' in filename:
    filename_base, ext = filename.rsplit('.', 1)
    if ext not in {'json', 'uasset', 'uexp'}:
        raise Exception('Unknown filename: {}'.format(filename))
    filename = filename_base

# Serialize it (might be already serialized, but don't bother checking)
subprocess.run([cmd_serialize, 'serialize', filename])

# Make sure it worked
json_path = '{}.json'.format(filename)
if not os.path.exists(json_path):
    raise Exception('Could not find {}'.format(json_path))

# Now loop through and generate a DOT graph
dot_path = '{}.dot'.format(filename)
with open(dot_path, 'wt') as odf:
    if '/' in filename:
        obj_name = filename.split('/')[-1]
    else:
        obj_name = filename
    print('digraph {} {{'.format(obj_name), file=odf)
    print('', file=odf)
    print('// Main Graph Label', file=odf)
    print('labelloc = "t";', file=odf)
    print('fontsize = 16;', file=odf)
    print('label = <{}>'.format(obj_name), file=odf)
    print('', file=odf)
    with open(json_path) as df:
        data = json.load(df)

        # First pass: construct all the main export nodes
        print('// Exports', file=odf)
        for idx, export in enumerate(data):
            idx += 1

            if export['_jwp_is_asset']:
                color = 'aquamarine1'
                asset = ' <i>(asset)</i>'
            else:
                color = 'aquamarine3'
                asset = ''
            export_title = '{}{}<br/>Type: {}<br/><i>(export {})</i>'.format(
                    export['_jwp_object_name'],
                    asset,
                    export['export_type'],
                    idx,
                    )
            print('export_{} [label=<{}> shape=rectangle style=filled fillcolor={}];'.format(
                idx,
                export_title,
                color,
                ), file=odf)
        print('', file=odf)

        # Second pass: recursively loop through the structure of each export, to generate links
        print('// Attributes and Links', file=odf)
        for idx, export in enumerate(data):
            idx += 1
            process_dict(odf, idx, export, [])
        print('', file=odf)

    print('}', file=odf)

# Now generate graphviz
final_path = '{}.{}'.format(filename, dot_output)
subprocess.run([cmd_dot, '-T{}'.format(dot_output), dot_path, '-o', final_path])

# ... and display it, if it worked
if os.path.exists(final_path):
    print('Wrote to {}!'.format(final_path))
    if dot_output in {'png', 'jpg', 'gif'}:
        subprocess.run([cmd_view, final_path])
else:
    print('ERROR: {} was not written'.format(final_path))

