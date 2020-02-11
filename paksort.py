#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

import re
import sys

pak_re = re.compile(r'^pakchunk(\d+)(optional)?-WindowsNoEditor(_(\d+)_P)?\.pak$')
# Making some assumptions about how DLC1 patch paks might look
dlc1_re = re.compile(r'^Dandelion(_(\d+)_P)?\.pak$')

dlc_step = 1000

class PakFile(object):

    def __init__(self, filename):
        self.filename = filename
        match = pak_re.match(self.filename)
        if match:
            self.paknum = int(match.group(1))
            if match.group(2):
                self.paknum += 0.5
            if match.group(3):
                self.patchnum = int(match.group(4))
            else:
                self.patchnum = -1
        else:
            match = dlc1_re.match(self.filename)
            if match:
                self.paknum = 1*dlc_step
                if match.group(1):
                    self.patchnum = int(match.group(2))
                else:
                    self.patchnum = -1
            else:
                raise Exception('Unknown pak file: {}'.format(filename))
        #print('{}: {}, {}'.format(self.filename, self.paknum, self.patchnum))

    def __lt__(self, other):
        return (self.paknum, self.patchnum) < (other.paknum, other.patchnum)

    def __repr__(self):
        return self.filename

files = []
for line in sys.stdin.readlines():
    files.append(PakFile(line.strip()))

for filename in sorted(files):
    print(filename)
