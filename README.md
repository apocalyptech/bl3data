Borderlands 3 Data Processing
=============================

A few utilities I use to extract BL3 data and massage it into a state
that's most useful for data inspection.  I Run BL3 on Linux using
Wine/Proton, so all of these assume Linux as well, so they're probably
not especially useful to most Windows users, alas.

- `link_paks.py`: I like to keep BL3's pakfiles sorted into dirs which
  correspond to the patches in which they were released.  This was easy
  enough to hand-manage when I was just adding them one at a time, as
  patches were released, but when I got the Steam version (in addition
  to EGS) and noticed that some of the checksums of pakfiles didn't
  match, it came time to automate.  Pass it a list of directories in 
  the current dir which start with `pak-`.  Each `pak-*` dir should have a
  `filelist.txt` in it, which is just a list of the pakfiles released
  in that patch.  This util will update symlinks based on a `-s`/`--store`
  argument, and now defaults to Steam.  Optionally, it'll also update
  our checksum files if it's passed `-c`/`--checksum`.  (It'll just
  append to the file.)

  - `checksums-sha256sum-egs.txt`: A list of sha256sum checksums for all
    the pakfiles in BL3, from Epic Games Store.  As of the Steam release,
    these often differ between platforms.

  - `checksums-sha256sum-steam.txt`: A list of sha256sum checksums for all
    the pakfiles in BL3, from Steam.  As of the Steam release, these
    often differ between platforms.

  - Note for both of these that in the patch *after* the Steam release
    (ie: the patch that came with DLC2), five new paks from the previous
    patch got overwritten entirely, so the checksums of five of the paks
    in `pak-2020-03-13-steam_xplay` have been removed, since they'll no
    longer match the live files.

- `uncompress.sh`: Used to call `UnrealPak.exe` via Wine to uncompress
  a bunch of PAK files.  Requires a `crypto.json` file to be populated
  using the BL3 encryption key.  (The key won't be stored on here; you'll
  have to find it elsewhere online.)  Should put all the new data in
  an `extractednew` directory.  You'd pass in one of the `pak-*` dirs
  from above into this.

- `gen_normalization_commands.py`: After extracting the data, the object
  names will often not exactly match the paths where they live on the
  filesystem.  This will generate a bunch of CLI commands which can be
  run to normalize that.  Give it at least a spot-check before running,
  though it seems mostly all right to me.  This util's been changed a
  bit since the initial runthrough, and hasn't been run against a
  completely-fresh unpack of all BL3 data, so be on the lookout for
  any problems!

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

### Sorting and Extraction

These are my notes of what I do when a new patch is released.  First,
to prep/extract the data:

1. Create a new `pak-YYYY-MM-DD-note` dir, with a `filelist.txt` inside
   which lists the new/update pakfiles
2. Use `link_paks.py` to symlink the pakfiles into the dir, for the given
   store, and generate updated checksums.  Repeat this for both stores,
   if you want both sets of checksums.
3. Uncompress the new `pak-*` dir using `uncompress.sh`.  This will leave
   an `extractednew` dir alongside the main `extracted` dir, with the
   new data.

If you don't care about my `pak-*` directory organization, you can just
lump all the paks in a single dir and `uncompress.sh` that.  It should
automatically call out to `paksort.py` to make sure things uncompress in
the right order to overwrite objects where appropriate.  (Note that that's
somewhat untested; since I do my per-patch directory structure personally,
I don't extract patches which overwrite data -- I think that `UnrealPak`
might actually refuse to overwrite by default, so be careful with that.)

### Massaging the Data

The first thing I tend to do at this point is get rid of files that I
don't personally care about, to save on HD space.  This'll include
audio/video and stuff, so if you want that data, maybe don't delete 'em.
Here's the stuff that I tend to delete outright, though (the bottom
three are found in various subdirs; I just use `find` to remove 'em):

- `*.wem`
- `*.bnk`
- `ShaderArchive-*`
- `PipelineCaches`
- `TritonData`

Then, I move any "bare" files in the `extractednew` dir up into the `Game` dir
(create if needed).  The script we use to get objects into their proper
paths doesn't like files *just* on the base dir, and rather than fix the
script, I tend to move 'em up so they get processed properly.

Then there's a bunch of stuff that doesn't really matter at all, at least
for the data I care about, but I sometimes look into regardless.  The actual
data objects will end up getting shuffled around to their "proper" places
in a later step anyway, so this basically just deals with files that *aren't*
`.uasset`/`.uexp`/`.umap`/`.ublk` files.  Regardless, you can probably mostly
ignore these bits if you want:

- Depending on the pakfiles that have been unpacked, there may be an
  `OakGame/Content` dir or a `Content` dir; I generally try to keep those
  at the same "level," so I may manually move them around after unpacking.
  It doesn't really matter much 'cause any game objects will get moved
  into their proper paths below.  I've not always been super consistent
  about that on my own unpacks.
- The file `InventorySerialNumberDatabase.dat` possibly moves around a bit
  depending on the Paks, too -- I tend to keep that in `/Game` itself, though
  it doesn't really matter much (though if you're not consistent then you
  may end up with multiple of the same file).  Again, doesn't really matter
  much; this file is useful when processing savegame item serial numbers
  is all.
- There's a `Localization` dir which might move around a bit, as well.  I
  tend to just sort of ignore that one, though theoretically it should
  get moved around so you're not left with multiple copies.

### Put Objects In the Proper Paths

Next, give `gen_normalize_commands.py` a run.  You'll want to redirect its
output to a file, check that file for the list of commands that was
generated, and then run those commands if they look good.  This'll move
all the object files around so that the filesystem paths match the in-game
object paths.  As mentioned above, the matching logic sort of doesn't know what
to do with files that are  *just* in the root directory; if you've got maps and
stuff sitting in there, move 'em into a temp directory (I use `Game`).  That or
I could fix the script, but that probably won't happen.

To get a list of files which the patch is going to overwrite, you can do
shenanigans like:

    (find . -type f -exec ls ../extracted/{} \;) 2>/dev/null
    (find . -type f -exec ls ../extractednew/{} \;) 2>/dev/null

Then compare the lists.

Anyway, once you're feeling good about the re-sorted objects, just copy the
new data on top of the existing data.

After all this, I'm aware of two objects which *are* wrong, and I'd forgotten
to investigate it while testing the whole process again, so for now just fix
them by hand.  Specifically, a couple of artifact parts end up with a
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

