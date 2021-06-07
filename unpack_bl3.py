#!/usr/bin/env python3

# Borderlands 3 Data Unpacking Script
# Copyright (C) 2020 apple1417 + apocalyptech
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND  # noqa: E501
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE1417 OR APOCALYPTECH BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Collection
from typing import ClassVar, Optional, cast

if platform.system() == "Windows":
    import winreg

""" Edit these variables as apropriate. """

# Default Install directory for Bordlerands 3.  Should contain an `Engine`
# and an `OakGame` directory.  If this doesn't exist, the utility will attempt
# to autodetect the BL3 install location.
# Can be overridden with --bl3install CLI arg
BL3_INSTALL_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 3"

# Directory to extract the pakfiles to.
# Can be overridden with --extract-to CLI arg
FINAL_EXTRACT_DIR = r"extracted_new"

# How to call UnrealPak, to do the extraction
UNREALPAK = r"UnrealPak.exe"

# Path to the crypto.json file, to decrypt the Pakfiles.  (Can be overridden
# with --crypto CLI arg.)
CRYPTO = r"crypto.json"

# If you only want to extract certain files/dirs, add them here
# This can be either a directory containing `.pak` files, or
# a path to a pakfile itself.
CUSTOM_PATH_LIST: list[str] = [

]

# Files/Directories to remove after doing the extraction (to
# save on some diskspace)
EXTRACTED_FILES_TO_DELETE: list[str] = [
    "*.wem",
    "*.bnk",
    "*ShaderArchive*",
]
EXTRACTED_DIRS_TO_DELETE: list[str] = [
    "*PipelineCaches*",
    "*TritonData*",
]

# Skip pakfiles which *only* have .wem audio data?  Be sure to remove "*.wem"
# from the auto-delete list, above, if you set this to False
SKIP_AUDIO_PAKS = True

# Linux users - to run UnrealPak.exe in Wine (as opposed to a native Linux
# version), set LINUX_USE_WINE here to True, and define your Wine executable
# and (optionally) WINEPREFIX environment variable to set.
LINUX_USE_WINE = True

WINE: Optional[str] = None
WINEPREFIX: Optional[str] = None
if LINUX_USE_WINE and platform.system() == "Linux":
    WINE = "wine64"
    WINEPREFIX = "/usr/local/winex/testing"

"""
Don't touch anything below here unless you know what you're doing.
================================================================================
"""

# Version Check
if sys.version_info < (3, 9):
    input("\nThis utility requires at least Python 3.9.  Hit Enter to exit.\n")
    raise RuntimeError("This utility requires at least Python 3.9")

# When excluding *.wem-only pakfiles entirely, and after deleting all the
# default stuff specified in EXTRACTED_*_TO_DELETE, this is the ratio of pakfile
# size to extracted size. (For reference, after the release of DLC5, it's 79GB
# of pakfiles -> 119GB extracted, though I used more exact numbers to get the
# ratio below).  Including the *.wem-only pakfiles (or altering the list of
# patterns to delete) would alter this ratio quite a bit.
PAK_SIZE_RATIO = 1.6

# sha256sum of the pakfile encryption key, to doublecheck user input
KEY_CHECKSUM = "45720b62a8a313ac59afe9792a0a1b8d034f6f65d37dd44a1caf578a832bdcba"  # noqa: E501

# Set WINEPREFIX env var if we've been told to
if WINEPREFIX:
    os.environ["WINEPREFIX"] = WINEPREFIX

STEAM_APP_ID = 397540

# /Game/Audio/Events/Characters/Player/BeastMaster/Char_BeastMaster/Anim/Skill_Screen/Abilities/WE_Char_Beastmaster_Anim_Skillscreen_Rakk_Attack_Proj_Start_Vox.uasset  # noqa: E501
# Technically it would be more correct to store the longest path in each pak
# somewhere, but generally people are going to extract everything anyway
LONGEST_PATH_LEN = 164

# Regex used to extract steam library locations from the `libraryfolders.vdf`
re_steam_libraries = re.compile(r"\t+\"\d+\"\t+\"(.+?)\"")


class PakFile:
    """
    Class used to sort PakFiles intelligently, so we can extract earlier ones
    before later ones.
    """

    re_pak: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<dir_prefix>.*[/\\])?pakchunk(?P<datagroup>\d+)(?P<optional>optional)?-WindowsNoEditor(_(?P<patchnum>\d+)_P)?\.pak$"  # noqa: E501
    )
    re_dlc: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<dir_prefix>.*[/\\])?(?P<dlcname>Dandelion|Hibiscus|Geranium|Alisma|Ixora|Ixora2)(_(?P<patchnum>\d+)_P)?\.pak$"  # noqa: E501
    )
    re_unpack_mount: ClassVar[re.Pattern[str]] = re.compile(
        r"Display: Mount point (?P<mountpoint>.*)$"
    )
    re_unpack_file: ClassVar[re.Pattern[str]] = re.compile(
        r"Display: \"(?P<filename>.*)\" offset"
    )
    re_normalize_plugins: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<firstpart>\w+)/Plugins/(?P<lastpart>.*)\s*$"
    )
    re_normalize_content: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<junk>.*/)?(?P<firstpart>\w+)/Content/(?P<lastpart>.*)\s*$"
    )
    re_extract: ClassVar[re.Pattern[str]] = re.compile(
        r"Display: Extracted \"(?P<filename>.*?)\" to "
    )
    dlc_nums: ClassVar[dict[str, int]] = {
        "Dandelion": 1,
        "Hibiscus": 2,
        "Geranium": 3,
        "Alisma": 4,
        "Ixora": 5,
        "Ixora2": 6,
    }
    dlc_step: ClassVar[int] = 1000

    # Which datagroups/paknums *only* ever contain *.wem audio data
    audio_nums: ClassVar[set[int]] = {2, 3, 85, 86, 87, 88, 89, 90, 91}

    content_firstpart_overrides: ClassVar[dict[str, str]] = {
        "OakGame": "Game",
        "Wwise": "WwiseEditor",
    }

    filename: str
    paknum: float
    patchnum: float
    size: int

    def __init__(self, filename: str) -> None:
        self.filename = filename
        match = self.re_pak.match(self.filename)
        if match:
            self.paknum = int(match.group("datagroup"))
            if match.group("optional") is not None:
                self.paknum += 0.5
            if match.group("patchnum") is not None:
                self.patchnum = int(match.group("patchnum"))
            else:
                self.patchnum = -1
        else:
            match = self.re_dlc.match(self.filename)
            if match:
                dlc_name = match.group("dlcname")
                if dlc_name not in self.dlc_nums:
                    raise RuntimeError(f"Unknown DLC Codename: {dlc_name}")
                self.paknum = self.dlc_step * self.dlc_nums[dlc_name]
                if match.group("patchnum") is not None:
                    self.patchnum = int(match.group("patchnum"))
                else:
                    self.patchnum = -1
            else:
                raise RuntimeError(f"Unknown pak file: {filename}")
        self.size = os.stat(self.filename, follow_symlinks=True).st_size

    def is_audio_only(self) -> bool:
        """
        Returns `True` if this pakfile is known to only contain *.wem Audio
        data, or `False` otherwise.
        """
        return self.paknum in self.audio_nums

    def get_filename_mapping(self, crypto: str) -> dict[str, str]:
        # First up: list the pak contents so we can determine the
        # real on-disk locations the files should go to.  We can't
        # get the mountpoint information without doing a separate
        # `-list`, alas.
        print("  Getting pakfile contents")

        p = launch_unrealpak(self.filename, "-list", f"-cryptokeys={crypto}")

        filename_mapping = {}
        mountpoint: str
        for line in iter(p.stdout.readline, ""):  # type: ignore
            if match := self.re_unpack_mount.search(line):
                mountpoint = match.group("mountpoint")
                if mountpoint.startswith("../../../"):
                    mountpoint = mountpoint[9:]
                elif mountpoint == "/":
                    # This seems to only ever show up in "empty" pakfiles,
                    # so it doesn't really matter.
                    mountpoint = ""

            elif match := self.re_unpack_file.search(line):
                if mountpoint is None:
                    raise RuntimeError("Found filename without knowing prefix")
                filename = match.group("filename")

                # Normalize the filename to find its "real" destination
                real_filename = f"{mountpoint}{filename}"
                if pluginmatch := self.re_normalize_plugins.match(real_filename):  # noqa: E501
                    real_filename = pluginmatch.group("lastpart")
                if contentmatch := self.re_normalize_content.match(real_filename):  # noqa: E501
                    firstpart = contentmatch.group("firstpart")
                    lastpart = contentmatch.group("lastpart")

                    # A couple of hardcodes in here, alas
                    if firstpart in self.content_firstpart_overrides:
                        firstpart = self.content_firstpart_overrides[firstpart]

                    real_filename = f"{firstpart}/{lastpart}"

                filename_mapping[filename] = real_filename

        return filename_mapping

    def extract(
        self,
        destination: str,
        crypto: str,
        expected_filenames: Optional[Collection[str]] = None
    ) -> None:
        """
        Call the UnrealPak executable (using Wine if requested, on Linux) to
        extract this pakfile into the `destination` directory.  Use `crypto` as
        the UnrealPak crypto config JSON file.  Returns a dictionary whose
        keys are the "raw" filenames extracted, and whose values are the
        normalized locations seen by the game itself (so object paths will
        match the file paths, for instance).
        """

        # Create our extraction directory if needed
        if not os.path.exists(destination):
            os.makedirs(destination, exist_ok=True)

        # Now do the unpacking
        print("  Unpacking files\r", end="")

        p = launch_unrealpak(
            self.filename,
            "-extract",
            destination,
            f"-cryptokeys={crypto}"
        )

        files_unpacked = 0
        total_files = len(expected_filenames) if expected_filenames else None

        last_report_time = 0.0

        for line in iter(p.stdout.readline, ""):  # type: ignore
            if match := self.re_extract.search(line):
                filename = match.group("filename")
                if expected_filenames and filename not in expected_filenames:
                    raise RuntimeError(
                        f"Unexpected filename extracted: {filename}"
                    )

                now = time.time()
                if files_unpacked % 50 == 0 or now > last_report_time + 1:
                    if total_files:
                        print(
                            f"  Unpacking files: {files_unpacked}/{total_files}\r",  # noqa: E501
                            end=""
                        )
                    else:
                        print(f"  Unpacking files: {files_unpacked}\r", end="")
                    last_report_time = now

                files_unpacked += 1

        if total_files:
            print(f"  Unpacking files: {files_unpacked}/{total_files}")
            if files_unpacked != total_files:
                raise RuntimeError(
                    f"Expected {total_files} files, only found {files_unpacked}"
                )
        else:
            print(f"  Unpacking files: {files_unpacked}")

    def __lt__(self, other: PakFile) -> bool:
        return (self.paknum, self.patchnum) < (other.paknum, other.patchnum)

    def __repr__(self) -> str:
        return self.filename


def launch_unrealpak(*args: str) -> subprocess.Popen[str]:
    """
    Launches unrealpak with the given command line args. Automatically uses wine
    if configured to, and translates FileNotFoundErrors to more intuitive
    RuntimeErrors.

    Pipes stdout and stderr, using utf8 encoding.

    Returns the Popen object from running unrealpak.
    """
    if WINE is not None:
        program = [WINE, UNREALPAK]
    else:
        program = [UNREALPAK]

    try:
        return subprocess.Popen(
            [*program, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except FileNotFoundError as e:
        # This is almost certainly because we couldn't find the UnrealPak
        # executable to run, but the exception given to the user in this case is
        # rather impenetrable.  Re-raise a different error which should point
        # them to the actual problem.
        raise RuntimeError(f"Could not find {program[0]} to unpack pak file: {e}") from None  # noqa: E501


def delete_extra_files(folder: str) -> None:
    """
    Given a folder, loop through and delete any files that we don't actually
    want to see in the final extraction.
    """
    files_deleted = 0
    dirs_deleted = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for pattern in EXTRACTED_FILES_TO_DELETE:
            for filename in fnmatch.filter(filenames, pattern):
                os.remove(os.path.join(dirpath, filename))
                files_deleted += 1

        for pattern in EXTRACTED_DIRS_TO_DELETE:
            for dirname in fnmatch.filter(dirnames, pattern):
                shutil.rmtree(
                    os.path.join(dirpath, dirname),
                    ignore_errors=True
                )
                dirs_deleted += 1

    reports = []
    if files_deleted > 0:
        if files_deleted == 1:
            files_plural = ""
        else:
            files_plural = "s"
        reports.append(f"{files_deleted} file{files_plural}")
    if dirs_deleted > 0:
        if dirs_deleted == 1:
            dirs_plural = ""
        else:
            dirs_plural = "s"
        reports.append(f"{dirs_deleted} dir{dirs_plural}")
    if len(reports) > 0:
        print(
            "  Pruned {} per config".format(
                " and ".join(reports),
            )
        )


def delete_empty_dirs(folder: str, delete_root: bool = True) -> bool:
    """
    Given a folder name, remove any empty dirs that are found recursively.

    Returns `True` if the root folder was deleted or `False` otherwise.
    """
    all_files = os.listdir(folder)
    file_set = set(all_files)
    for filename in all_files:
        full_filename = os.path.join(folder, filename)
        if not os.path.isdir(full_filename):
            continue

        deleted_root = delete_empty_dirs(full_filename)
        if deleted_root:
            file_set.remove(filename)

    if len(file_set) == 0 and delete_root:
        os.rmdir(folder)
        return True

    return False


def normalize_pak_files(
    temp_folder: str,
    final_folder: str,
    filename_mapping: dict[str, str]
) -> None:
    """
    Move extracted pakfile contents from their temporary extraction point
    `temp_folder`, into their ultimate destination `final_folder`, using
    `filename_mapping` to translate the paths to their in-game values.
    Will attempt to clear out `temp_folder` afterwards, and will raise
    a RuntimeError if unable to do so.
    """
    for temp_filename, final_filename in filename_mapping.items():
        temp_filename_full = os.path.join(temp_folder, temp_filename)
        if os.path.exists(temp_filename_full):
            final_filename_full = os.path.join(final_folder, final_filename)

            # Normalize for OS
            final_filename_full = final_filename_full.replace("/", os.path.sep)
            temp_filename_full = temp_filename_full.replace("/", os.path.sep)

            # Do the moves
            final_dirname = os.path.dirname(final_filename_full)
            os.makedirs(final_dirname, exist_ok=True)
            os.rename(temp_filename_full, final_filename_full)

    if not delete_empty_dirs(temp_folder):
        raise RuntimeError(f"Could not delete temporary folder {temp_folder}")


def get_install_paks(install_root: str) -> list[str]:
    """
    Given an `install_root` which points to the root install of Borderlands 3,
    return all pakfiles installed.
    """
    # We should maybe just do an os.walk() from here and grab literally
    # everything that's a `.pak` file, but maybe someone's been moving things
    # around a bit for data injection purposes or whatever?  So we'll be a bit
    # more clever and look at the locations we know pakfiles should be.
    pakfiles = []

    base_root = os.path.join(install_root, "OakGame", "Content", "Paks")
    for base_pak in os.listdir(base_root):
        if base_pak.endswith(".pak"):
            pakfiles.append(os.path.join(base_root, base_pak))

    dlc_root = os.path.join(install_root, "OakGame", "AdditionalContent")
    for dlcname in os.listdir(dlc_root):
        dlc_full_path = os.path.join(dlc_root, dlcname, "Paks")
        for dlc_pak in os.listdir(dlc_full_path):
            if dlc_pak.endswith(".pak"):
                pakfiles.append(os.path.join(dlc_full_path, dlc_pak))

    return pakfiles


def find_default_bl3_install() -> str:
    """
    Attepts to find the BL3 install folder.  Returns `BL3_INSTALL_DIR` if it
    exists, or if it can't find a better folder to work from.
    """
    if os.path.exists(BL3_INSTALL_DIR) and os.path.isdir(BL3_INSTALL_DIR):
        return BL3_INSTALL_DIR

    epic_install_dirs: dict[str, str] = {
        "Windows": r"C:\Program Files\Epic Games\Borderlands3",
        "Darwin": r"",
        "Linux": r"",
    }
    epic_install = os.path.expanduser(epic_install_dirs[platform.system()])
    if os.path.exists(epic_install) and os.path.isdir(epic_install):
        return epic_install

    if platform.system() == "Windows":
        try:
            sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            sub_key += rf"\\Steam App {STEAM_APP_ID}"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key)
            install, key_type = winreg.QueryValueEx(key, "InstallLocation")
            if (
                key_type == winreg.REG_SZ
                and os.path.exists(install)
                and os.path.isdir(install)
            ):
                return cast(str, install)
        except FileNotFoundError:
            pass

    steamapps_dirs: dict[str, str] = {
        "Windows": r"C:\Program Files (x86)\Steam\steamapps",
        "Darwin": r"~/Library/Application Support/Steam/steamapps",
        "Linux": r"~/.steam/steam/steamapps",
    }
    steamapps = os.path.expanduser(steamapps_dirs[platform.system()])

    all_steamapps_folders = {steamapps}
    try:
        with open(os.path.join(steamapps, "libraryfolders.vdf")) as file:
            for match in re_steam_libraries.finditer(file.read()):
                library = match.group(1).replace(r"\\", os.path.sep)
                if os.path.exists(library) and os.path.isdir(library):
                    all_steamapps_folders.add(
                        os.path.join(library, "steamapps")
                    )
    except FileNotFoundError:
        return BL3_INSTALL_DIR

    app_manifest = f"appmanifest_{STEAM_APP_ID}.acf"
    for folder in all_steamapps_folders:
        manifest_file = os.path.join(folder, app_manifest)
        if os.path.exists(manifest_file) and os.path.isfile(manifest_file):
            bl3_install = os.path.join(folder, "common", "Borderlands 3")
            if os.path.exists(bl3_install) and os.path.isdir(bl3_install):
                return bl3_install

    return BL3_INSTALL_DIR


if __name__ == "__main__":
    # Parse args
    parser = argparse.ArgumentParser(
        description="Unpack Borderlands 3 PAK files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
            Without arguments, this utility will unpack all pakfiles found in
            the configured Borderlands 3 install root.  To specify individual
            directories full of pakfiles, or individual pakfiles, pass them as
            arguments.
        """,
    )

    parser.add_argument(
        "--extract-to",
        type=str,
        default=FINAL_EXTRACT_DIR,
        help="Directory to extract data into",
    )

    parser.add_argument(
        "--bl3install",
        type=str,
        default=find_default_bl3_install(),
        help="Install root for Borderlands 3",
    )

    parser.add_argument(
        "--crypto",
        type=str,
        default=CRYPTO,
        help="Path to crypto.json file, for pakfile decryption",
    )

    parser.add_argument(
        "--no-disk-check",
        action="store_true",
        help="Don't check for available diskspace before doing extraction",
    )

    parser.add_argument(
        "--no-path-len-check",
        action="store_true",
        help="Don't check maximum pathname length before doing extraction",
    )

    parser.add_argument(
        "path",
        nargs="*",
        help="""
            Path(s) to extract.  Can either be pakfiles themselves, or
            directories containing pakfiles.
        """,
    )

    args = parser.parse_args()

    # Use a try/finally to require the user to hit enter before closing, so
    # Windows users won't have the window just disappear if we've been
    # double-clicked from Explorer
    try:
        # Figure out what files/dirs we'll be acting on
        if len(CUSTOM_PATH_LIST) > 0:
            paths_to_add = CUSTOM_PATH_LIST
            report = "custom override list"
        elif args.path:
            paths_to_add = args.path
            report = "commandline arguments"
        else:
            paths_to_add = get_install_paks(args.bl3install)
            report = args.bl3install

        # Make sure our given paths are what we expect
        proposed_pak_files = []
        for pathname in paths_to_add:
            if os.path.isdir(pathname):
                for filename in os.listdir(pathname):
                    if filename.endswith(".pak"):
                        proposed_pak_files.append(
                            PakFile(os.path.join(pathname, filename))
                        )
            else:
                if pathname.endswith(".pak"):
                    proposed_pak_files.append(PakFile(pathname))
                else:
                    raise ValueError(
                        f"Specified file {pathname} is not a .pak file"
                    )

        # Strip out audio-only pakfiles if we've been configured to do so
        all_pak_files = []
        for pf in proposed_pak_files:
            if SKIP_AUDIO_PAKS and pf.is_audio_only():
                print(
                    f"Skipping {pf.filename} because it is audio data only..."
                )
                continue
            all_pak_files.append(pf)

        # Do we actually have files to work with?
        if not all_pak_files:
            raise ValueError("No pakfiles found to process!")
        print(f"\nProcessing {len(all_pak_files)} pakfiles from {report}")
        print("")
        if len(EXTRACTED_FILES_TO_DELETE) > 0:
            print("Pruning files matching:")
            for pattern in EXTRACTED_FILES_TO_DELETE:
                print(f" - {pattern}")
            print("")
        if len(EXTRACTED_DIRS_TO_DELETE) > 0:
            print("Pruning directories matching:")
            for pattern in EXTRACTED_DIRS_TO_DELETE:
                print(f" - {pattern}")
            print("")

        # Create our final extraction dir, if need be.
        final_extract = os.path.abspath(args.extract_to)
        os.makedirs(final_extract, exist_ok=True)

        # Check for diskspace, unless we've been told not to.
        if not args.no_disk_check:
            # Compute how much diskspace we think the extraction might take
            # First the raw pakfile size
            required_size = sum(pf.size for pf in all_pak_files)
            # Now add in more for the maximum-sized pakfile, since it'll briefly
            # be on disk twice
            required_size += max(pf.size for pf in all_pak_files)
            # Apply our estimated extraction ratio, convert to gigs, round up,
            # and add an extra 1 for good measure
            required_gb = math.ceil(
                required_size * PAK_SIZE_RATIO / 1024 / 1024 / 1024
            ) + 1

            # Grab current free space
            _, _, free_space = shutil.disk_usage(final_extract)
            free_gb = math.ceil(free_space / 1024 / 1024 / 1024)

            # Warn if we don't think we have enough
            if required_gb > free_gb:
                print("""
WARNING: We predict that the extraction will take {}G of free space, but it
looks like only {}G is currently available.
"""[1:].format(required_gb, free_gb))

                user_input = input(
                    "Proceed with extraction anyway [y/N]? "
                ).strip()[:1].lower()
                if user_input != "y":
                    print("\nOkay, exiting...\n")
                    sys.exit(1)

        # Check if the extraction may result in a pathname that's too long
        if not args.no_path_len_check:
            # Using wine still inherits the windows max len
            max_path_len = 260
            extract_path_len = len(final_extract) + LONGEST_PATH_LEN

            if extract_path_len > max_path_len:
                print("""
WARNING: We predict that the extraction will create a file path of length {},
which is greater than the system maximum {}. This may cause extraction to fail.
"""[1:].format(extract_path_len, max_path_len))

                user_input = input(
                    "Proceed with extraction anyway [y/N]? "
                ).strip()[:1].lower()
                if user_input != "y":
                    print("\nOkay, exiting...\n")
                    sys.exit(1)

        # Find out if we have a crypto.json file or not, and prompt the user for
        # an encryption key if we don't
        if not os.path.isfile(args.crypto):
            # The normal value will he `crypto.json`, using `{crypto___}` to get
            # the same length
            print("""
The UnrealPak crypto-config file '{crypto___}' could not be found!

Please enter the BL3 Pakfile Encryption Key below to automatically create one."
An internet search for 'borderlands 3 pakfile aes key' should bring it up."

If you prefer to create your own '{crypto___}' file, you can use the sample at"
'crypto.json.sample'.
"""[1:].format(crypto___=args.crypto))

            key_input = input("Input Encryption Key> ").strip().lower()
            if key_input.startswith("0x"):
                key_input = key_input[2:]
            if not re.match(r"^[0-9a-f]{64}$", key_input):
                raise ValueError(
                    "Error: Encryption key must consist of 64 hex digits"
                )

            key_data = bytes.fromhex(key_input)
            key_b64 = base64.b64encode(key_data)
            m = hashlib.sha256()
            m.update(key_data)
            key_sha256 = m.hexdigest()

            if key_sha256 != KEY_CHECKSUM:
                print("""

WARNING: The key you put in does not appear to match the actual BL3 pakfile
encryption key.  Do you actually want to proceed?
"""[1:])

                user_input = input(
                    f"Proceed with creating '{args.crypto}' [y/N]? "
                ).strip()[:1].lower()
                if user_input != "y":
                    print("\nOkay, exiting...\n")
                    sys.exit(1)

            to_json = {
                "$types": {
                    "UnrealBuildTool.EncryptionAndSigning+CryptoSettings, UnrealBuildTool, Version=4.0.0.0, Culture=neutral, PublicKeyToken=null": "1",  # noqa: E501
                    "UnrealBuildTool.EncryptionAndSigning+EncryptionKey, UnrealBuildTool, Version=4.0.0.0, Culture=neutral, PublicKeyToken=null": "2",  # noqa: E501
                },
                "$type": "1",
                "EncryptionKey": {
                    "$type": "2",
                    "Name": None,
                    "Guid": None,
                    "Key": key_b64.decode("latin1"),
                },
                "SigningKey": None,
                "bEnablePakSigning": False,
                "bEnablePakIndexEncryption": True,
                "bEnablePakIniEncryption": True,
                "bEnablePakUAssetEncryption": False,
                "bEnablePakFullAssetEncryption": False,
                "bDataCryptoRequired": True,
                "SecondaryEncryptionKeys": []
            }
            with open(args.crypto, "w") as df:
                json.dump(to_json, df, indent=4)

            print(f"\nCreated '{args.crypto}'!  Continuing...\n")

        # Set up our temporary extraction subdir location (clear it out, first)
        tmp_extract = os.path.abspath(
            os.path.join(args.extract_to, "_unpack_bl3_tmp")
        )
        shutil.rmtree(tmp_extract, ignore_errors=True)

        crypto_path = os.path.abspath(args.crypto)

        # Loop through all pakfiles and process
        for pakfile in sorted(all_pak_files):
            report_str = f"Processing file {pakfile}..."
            print(report_str)
            print("=" * len(report_str) + "\n")

            filename_mapping = pakfile.get_filename_mapping(crypto_path)
            pakfile.extract(tmp_extract, crypto_path, filename_mapping.keys())
            delete_extra_files(tmp_extract)

            print("  Moving files to in-game locations")
            normalize_pak_files(tmp_extract, final_extract, filename_mapping)

            print("  Done!")
            print()

    except Exception as e:
        print("""
Error encountered while running: {}

Full traceback follows:
"""[1:].format(e))
        traceback.print_exc(file=sys.stdout)

    finally:
        input("\nFinished.  Hit Enter to exit.\n")
