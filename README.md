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
directory and extracting using `uncompress.sh`.

Move data from `OakGame/Content` into the "base" extracted dir.
Oct 24 2019 patch also had just a bare `Content` dir instead, which seemed
like it needed merging.

Files to remove from extracted paks:

- `*.wem`
- `*.bnk`
- `ShaderArchive-*`
- `PipelineCaches`

Then give `gen_normalize_commands.py` a run, check the output, and run the
commands, so that the object names match the filesystem paths.

To get a list of files which the patch is going to overwrite, you can do
shenanigans like:

    (find . -type f -exec ls ../extracted/{} \;) 2>/dev/null
    (find . -type f -exec ls ../extracted-patch-2019-10-03/{} \;) 2>/dev/null

In Dandelion DLC (moxxi), there was an `OakGame` dir at the root there,
which we've previously had inside `Game`.  Sort of doesn't matter since
there's no uasset/umap files in there, but worth mentioning

Note too that the matching logic doesn't do well with files *just* in the
root directory; if you've got maps and stuff sitting in there, move 'em
into a temp directory (or fix the script, of course, but eh)

As of Broken Hearts, I'd also manually moved the `Localization` dir up
into `Game` (that's honestly probably not right, but whatever, it's not
game objects).  Also moved `InventorySerialNumberDatabase.dat` into
`Game`.

