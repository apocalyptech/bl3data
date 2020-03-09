Borderlands 3 Data Processing
=============================

A few utilities I use to extract BL3 data and massage it into a state
that's most useful for data inspection.  I Run BL3 on Linux using
Wine/Proton, so all of these assume Linux as well, so they're probably
not especially useful to most Windows users, alas.

- `uncompress.sh`: Used to call `UnrealPak.exe` via Wine to uncompress
  a bunch of PAK files.  Requires a `crypto.json` file to be populated
  using the BL3 encryption key.  (The key won't be stored on here; you'll
  have to find it elsewhere online.)  Should put all the new data in
  an `extractednew` directory.

- `gen_normalization_commands.py`: After extracting the data, the object
  names will often not exactly match the paths where they live on the
  filesystem.  This will generate a bunch of CLI commands which can be
  run to normalize that.  Give it at least a spot-check before running,
  though it seems mostly all right to me.  This util's been changed a
  bit since the initial runthrough, and hasn't been run against a
  completely-fresh unpack of all BL3 data, so be on the lookout for
  any problems!

- `gen_checksums.py`: Just used to append to `checksums-sha256sum.txt`
  when patches have been released.

  - `checksums-sha256sum.txt`: Just a list of sha256sum checksums for all
    the pakfiles in BL3.  They're organized by patch date, so you can
    easily see which pak files were added at what point in BL3's history.

- `find_dup_packs.py`: Little utility to see if duplicate PAK files
  exist in any dirs.  Just some sanity checks for myself.

- `paksort.py`: Sorts PAK files passed on STDIN "intelligently," rather
  than just alphanumerically (which would otherwise put `pakchunk21`
  inbetween `pakchunk2` and `pakchunk3`, for instance).  Handles the
  patch filename conventions as well, so patches will show up after
  the files they patch.  Basically this can be used to define an order
  of unpacking.

New-Data Steps
--------------

These are my notes of what I do when a new patch is released, after
extracting all the new `.pak` files into a separate `pak-YYYY-MM-DD-note`
directory and extracting using `uncompress.sh`.  This can also be used
to "step through" uncompressing BL3 data freshly, if you wanted to make
sure to unpack the pakfiles in the right order.  Just uncompress each
patch at a time, do these steps, and merge 'em in.

First off, a few things which don't *really* matter at all (at least for
the data I care about), but I tend to handle regardless.  The data objects
themselves will get moved around properly by a script a little further
down, regardless, so you can probably just ignore these bits if you want:

- Depending on the pakfiles that have been unpacked, there may be an
  `OakGame/Content` dir or a `Content` dir; I generally try to keep those
  at the same "level," so I may manually move them around after unpacking.
  It doesn't really matter much 'cause any game objects will get moved
  into their proper paths below.  I've not always been super consistent
  about that on my own unpacks.
- The file `InventorySerialNumberDatabase.dat` possibly moves around a bit
  depending on the Paks, too -- I tend to keep that in `/Game` itself, though
  it doesn't really matter much (though if you're not consistent then you
  may end up with multiple of the same file.  (Again, doesn't really matter
  much; this file is useful when processing savegame item serial numbers
  is all.)
- There's a `Localization` dir which might move around a bit, as well.  I
  tend to just sort of ignore that one, though theoretically it should
  get moved around so you're not left with multiple copies.

Now, move any "bare" files in the `extractednew` dir up into the `Game` dir
(create if needed).  The script we use to get objects into their proper
paths doesn't like files just on the base dir.

Files to remove from extracted paks (just to save on space; stuff I don't
personally care about.  This'll include audio/video and stuff, so if you
want that data, maybe you don't want to delete all of it):

- `*.wem`
- `*.bnk`
- `ShaderArchive-*`
- `PipelineCaches`
- `TritonData`

Then give `gen_normalize_commands.py` a run, check the output, and run the
commands, so that the object names match the filesystem paths.  As mentioned
above, the matching logic sort of doesn't know what to do with files that
are  *just* in the root directory; if you've got maps and stuff sitting in
there, move 'em into a temp directory (I use `Game`).  That or I could fix
the script, but that probably won't happen.

To get a list of files which the patch is going to overwrite, you can do
shenanigans like:

    (find . -type f -exec ls ../extracted/{} \;) 2>/dev/null
    (find . -type f -exec ls ../extracted-patch-2019-10-03/{} \;) 2>/dev/null

Then compare the lists.

Anyway, once you're feeling good about the re-sorted objects, just copy the
new data on top of the existing data.

After all this, I'm aware of two objects which *are* wrong, and I'd forgotten
to investigigate it while testing the whole process again, so for now just fix
them by hand, if you think you might want to serialize these objects using my
data library routines.  Specifically, a couple of artifact parts end up with a
`_2` suffix in their filename.  No idea if that's due to the original filenames
from the PAK file or not...

- `/Game/Gear/Artifacts/_Design/PartSets/SecondaryStats/Elemental/Artifact_Part_Stats_CryoDamage_2`
- `/Game/Gear/Artifacts/_Design/PartSets/SecondaryStats/Elemental/Artifact_Part_Stats_FireDamage_2`

In both cases, just remove the `_2` entirely from both `.uasset` and `.uexp`.

License
-------

All code in this project is is licensed under the
[New/Modified (3-Clause) BSD License](https://opensource.org/licenses/BSD-3-Clause).
A copy can be found in [COPYING.txt](COPYING.txt).

