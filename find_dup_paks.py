#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

import os
import itertools

paks = {}
for filename in os.listdir('.'):
    if filename.startswith('pak-'):
        paks[filename] = set()
        for pakname in os.listdir(filename):
            if pakname.endswith('.pak'):
                paks[filename].add(pakname)

# Now find duplicates.
for ((pakdir1, paks1), (pakdir2, paks2)) in itertools.combinations(paks.items(), 2):
    combined = paks1 & paks2
    if len(combined) > 0:
        print('{} and {} share these:'.format(pakdir1, pakdir2))
        print(combined)
        print('')
