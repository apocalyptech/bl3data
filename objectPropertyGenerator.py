#!/usr/bin/env python3
# vim: set noexpandtab copyindent preserveindent softtabstop=0 shiftwidth=4 tabstop=4:

# Borderlands 3 Object Property Generator
# Copyright (C) 2020 FromDarkHell
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
import lzma
import argparse
import traceback
from datetime import datetime

try:
	import colorama
	colorSupported = True
except ModuleNotFoundError:
	colorSupported = False

# Taken from FromDarkHell's original version posted here:
#   https://gist.github.com/FromDarkHell/3a2d67ed7d05364d5651823018dea3d7
#
# ... and added to this repo with FDH's permission.  Thx!
#
# Changes from FDH's orig:
#  - Modified default paths to suit my own env
#  - Read/Write from LZMA-compressed files
#  - Use -g/--generate to force cache generation, instead of asking
#  - Case-insensitive retrieval/searching (makes search output less nice, but eh)
#  - Input loop instead of just doing a single query
#  - If property name isn't found, fall back to search
#  - Colors that hurt c0dycode's eyes

# Change your data path and cache file here
dataDir = r"/home/pez/bl3_egs_root/OakGame/Binaries/Win64/data/main_menu"
cacheFile = "/home/pez/.local/share/bl3objectprops/props.json.xz"

def generatePropertyData(directoryPath, cacheFile):

	namesFileName = os.path.join(directoryPath, "UE4Tools_NamesDump.txt")
	if os.path.exists(namesFileName):
		namesFile = open(namesFileName, "r")
	elif os.path.exists(namesFileName + ".xz"):
		namesFile = lzma.open(namesFileName + ".xz", "rt", encoding="latin1")
	else:
		raise Exception(f"Could not find {namesFileName}")

	objectsFileName = os.path.join(directoryPath, "UE4Tools_ObjectsDump.txt")
	if os.path.exists(objectsFileName):
		objectsFile = open(objectsFileName, "r")
	elif os.path.exists(objectsFileName + ".xz"):
		objectsFile = lzma.open(objectsFileName + ".xz", "rt", encoding="latin1")
	else:
		raise Exception(f"Could not find {objectsFileName}")

	propertyTypes, classes, functions = [],[],[]

	executionTime = datetime.now()

	print("Reading classes...")
	for line in namesFile.readlines():
		if "/" in line: continue

		c = line.split('] ')[1].replace('\n','')
		classes += [c]

		# Slightly dodgy assumption here, a possible property could actually include non-alphabetical chars but *ehh*
		if(('property' in c.lower() or 'function' in c.lower()) and c.isalpha()): propertyTypes += [c]

	print(f"Found total {len(classes)} classes in {(datetime.now() - executionTime).total_seconds()}")
	print(f"Total Property Types: {len(propertyTypes)}\n")

	print("Reading object dumps...")

	propertyTypes.remove('MaterialFunction')
	propertyTypes.remove('DialogSelectorFunction')

	i = 0
	classProperties = {
		#"className": [
		#	{"propertyName":"propertyType"}
		#]
	}

	executionTime = datetime.now()
	for line in objectsFile.readlines():
		try:
			# [00000011] 00000000168C0C00 Class Engine.BlueprintFunctionLibrary
			mainInfo = line.split(' ')[2] # Everything past the hex addresses.

			lineProperty = mainInfo.split(' ')[0] # From above, it'll get `Class`
			objectData = line.split(' ')[3].replace('\n','') # In the above example it'll get `Engine.BlueprintFunctionLibrary`

			if lineProperty not in propertyTypes or "default" in objectData.lower() or "__" in objectData.lower(): continue

			if lineProperty == "Function":
				functions += objectData
				continue
			objectClass = objectData[objectData.find('.')+1:].split('.')[0]
			objectClassLower = objectClass.lower()
			propertyName = objectData[objectData.find('.')+1:]
			propertyName = propertyName[propertyName.find('.')+1:]
			# print(f"Reading property {propertyName} on {objectClass} as type of {lineProperty} on line: {line}")

			currentProperties = []
			if(objectClassLower in classProperties): currentProperties = classProperties[objectClassLower]
			currentProperties += [{propertyName:lineProperty}]

			classProperties.update({objectClassLower : currentProperties })
		except:
			print(f"Unable to parse file line: {line}: {traceback.format_exc()}")
			raise

	print(f"Found properties for total classes of {len(classProperties)}")
	print(f"Read properties in {(datetime.now() - executionTime).total_seconds()} seconds")

	# Make the cache directory if we have to
	cacheDir = os.path.dirname(cacheFile)
	if not os.path.exists(cacheDir):
		os.makedirs(cacheDir, exist_ok=True)

	# Now write out the cache file
	if cacheFile.endswith('.xz'):
		oFile = lzma.open(cacheFile, "wt")
	else:
		oFile = open(cacheFile, "w")
	json.dump(classProperties, oFile, indent=4, sort_keys=True)
	oFile.close()

# Arguments
parser = argparse.ArgumentParser(
		description="BL3 Object Properties",
		epilog="NOTE: color output requires installation of the `colorama` Python library",
		)

parser.add_argument('-g', '--generate',
		action='store_true',
		help='Force generation of property cache')

colorgroup = parser.add_mutually_exclusive_group()

colorgroup.add_argument('-c', '--color',
		action='store_true',
		help='Use colors on output (defaults to looking good on black background)')

colorgroup.add_argument('-w', '--whitecolor',
		action='store_true',
		help='Use colors on output (for white backgrounds)')

args = parser.parse_args()

# Colors!
color_prompt = ''
color_error = ''
color_searchres = ''
color_propres = ''
color_reset = ''
if colorSupported:
	if args.color:
		color_prompt = colorama.Fore.BLUE + colorama.Style.BRIGHT
		color_error = colorama.Fore.RED
		color_searchres = colorama.Fore.CYAN
		color_propres = colorama.Fore.GREEN
		color_reset = colorama.Style.RESET_ALL
		colorama.init(autoreset=True)
	elif args.whitecolor:
		color_prompt = colorama.Fore.BLUE
		color_error = colorama.Fore.RED
		color_searchres = colorama.Fore.CYAN
		color_propres = colorama.Fore.GREEN
		color_reset = colorama.Style.RESET_ALL
		colorama.init(autoreset=True)
elif args.color or args.whitecolor:
	print('WARNING: `colorama` module not found; try `pip3 install colorama` for color support')

# Generate cache if we need to
if not os.path.exists(cacheFile) or args.generate:
	print("Generating property data...")
	generatePropertyData(dataDir, cacheFile)

# Now our property data was generated or already exists. 
if cacheFile.endswith(".xz"):
	propertyOutput = lzma.open(cacheFile, 'rt')
else:
	propertyOutput = open(cacheFile)
jsonData = json.load(propertyOutput)
propertyOutput.close()

# Input loop
while True:
	print("")
	print(f"{color_prompt}[S]earch, Get [P]roperties, or [Q]uit?{color_reset}", end=" ")

	searchOrProperties = input().strip().lower()
	print("")
	if searchOrProperties == "q":
		break
	elif searchOrProperties != 's' and searchOrProperties != 'p':
		print(f"{color_error}Unknown type... Try again.")
		continue

	searchTerm = None
	if searchOrProperties == 'p':
		print("Class to get properties of:", end=' ')
		classToSearch = input()
		print("")
		if classToSearch in jsonData:
			print(f"Found properties of {classToSearch}")
			combinedOutput = json.dumps(jsonData[classToSearch.lower()], sort_keys=True).replace('}, ','\n').replace('{','').replace('}]','').replace('[','')
			print(f"{color_propres}Properties: \n{combinedOutput}")
			continue
		else:
			print(f"{color_error}'{classToSearch}' not found, searching instead...")
			searchOrProperties = 's'
			searchTerm = classToSearch

	if searchOrProperties == 's':
		storedClasses = jsonData.keys()
		if not searchTerm:
			print("Search for:", end=' ')
			searchTerm = input()
		results = []
		for c in storedClasses:
			if(searchTerm.lower() in c.lower()):
				results += [c]
		if not results:
			print(f"{color_error}Unable to find results for {searchTerm}")
		else:
			print("Found results: ")
			for res in results:
				print(f"{color_searchres} - {res}")

