#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2020-2022 CJ Kucera (cj@apocalyptech.com)
# 
# This software is provided 'as-is', without any express or implied warranty.
# In no event will the authors be held liable for any damages arising from
# the use of this software.
# 
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
# 
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software in a
#    product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 
# 3. This notice may not be removed or altered from any source distribution.

import os
import sys
import argparse
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

###
### Decryption bit.  Thanks to Baysix for this!
###
### Basically, the encryption key for the file is stored in the final 32 bits
### of the file, but *that* key is encrypted using the first 32 bits of the
### encrypted file itself.  Just an extra little bit of obfuscation for us all.
###

def decrypt(key, data):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data)

def decrypt_db(data):
    """
    Returns a tuple -- the first element is the encryption key, and the
    second is the decrypted file data.
    """
    key = decrypt(data[:32], data[-32:])
    return (key, decrypt(key, data[:-32]).rstrip(b'\x00'))

def encrypt(key, data):
    cipher = AES.new(key, AES.MODE_ECB)
    # AES uses 16-byte blocksize; pad with NULLs if needed.  This isn't
    # necessarily the best way to pad, but it's what GBX seem to be
    # doing, so that's what we're doing, too.
    if len(data) % 16 == 0:
        num_to_pad = 0
    else:
        num_to_pad = 16 - (len(data) % 16)
    return cipher.encrypt(data + b'\x00'*num_to_pad)

def encrypt_db(key, data):
    main_bit = encrypt(key, data)
    return main_bit + encrypt(main_bit[:32], key)

def check_overwrite(filename, args):
    if os.path.exists(filename):
        if args.force:
            print(f'WARNING: Overwriting {filename}')
        else:
            resp = input(f'{filename} already exists!  Overwrite [y/N]? ')
            resp = resp.strip().lower()
            if resp == 'y':
                return
            else:
                print('Exiting!')
                sys.exit(1)

def main():

    parser = argparse.ArgumentParser(
            description='Decrypt or Encrypt InventorySerialNumberDatabase.dat files from BL3/TTWL',
            )

    action = parser.add_mutually_exclusive_group(required=True)

    action.add_argument('-d', '--decrypt',
            action='store_true',
            help="""Decrypt the specified file.  The decrypted filename will
            default to the same filename but with an extra `.decrypted`
            extension.  Will also write out the key to a file with a `.key`
            extension.
            """,
            )

    action.add_argument('-e', '--encrypt',
            action='store_true',
            help="""Encrypt the specified file.  If the specified file
            has a `.decrypted` extension, the output filename will replace
            `.decrypted` with `.new`, and the key will be read from the
            related file with an extension of `.key`.  Otherwise, you must
            manually specify the output filename and the key filename.
            """,
            )

    parser.add_argument('-k', '--key',
            type=str,
            help="""Use the specified file for writing/reading the encryption key,
            rather than the defaults.
            """,
            )

    parser.add_argument('-o', '--output',
            type=str,
            help="Use the specified output filename, rather than the defaults.",
            )

    parser.add_argument('-r', '--randomize',
            action='store_true',
            help='Randomize the encryption key instead of reading the previous one.',
            )

    parser.add_argument('-f', '--force',
            action='store_true',
            help='Force overwrite of files, if they already exist.',
            )

    parser.add_argument('filename',
            nargs=1,
            help='Filename to decrypt/encrypt',
            )

    # Parse args
    args = parser.parse_args()
    args.filename = args.filename[0]

    # Figure out what filenames we're using
    if args.decrypt:
        output_filename = '{}.decrypted'.format(args.filename)
        key_filename = '{}.key'.format(args.filename)
    else:
        output_filename = None
        key_filename = None
        if args.filename.endswith('.decrypted'):
            output_filename = '{}.new'.format(args.filename[:-10])
            key_filename = '{}.key'.format(args.filename[:-10])
    if args.output:
        output_filename = args.output
    if args.key:
        key_filename = args.key

    # Check to make sure we've got the filenames we need
    if output_filename is None:
        raise RuntimeError('No output filename specified')
    if key_filename is None:
        raise RuntimeError('No key filename specified')

    # Check to see if our output file already exists
    check_overwrite(output_filename, args)

    # Do the work
    if args.decrypt:

        # Check to see if our output key file already exists
        check_overwrite(key_filename, args)

        # Decrypt!
        with open(args.filename, 'rb') as df:
            with open(output_filename, 'wb') as odf:
                with open(key_filename, 'wb') as kdf:
                    key, decrypted = decrypt_db(df.read())
                    odf.write(decrypted)
                    kdf.write(key)
        print(f'Wrote to: {output_filename}')
        print(f'Wrote key to: {key_filename}')

    else:

        # Read in our key (or randomize a new one)
        if args.randomize:
            key = get_random_bytes(32)
        else:
            if not os.path.exists(key_filename):
                print(f'WARNING: {key_filename} does not exist.  Decrypt the original file, first.')
                sys.exit(1)
            with open(key_filename, 'rb') as kdf:
                key = kdf.read()

        # Encrypt!
        with open(args.filename, 'rb') as df:
            with open(output_filename, 'wb') as odf:
                odf.write(encrypt_db(key, df.read()))
        print(f'Wrote to: {output_filename}')

if __name__ == '__main__':
    main()

