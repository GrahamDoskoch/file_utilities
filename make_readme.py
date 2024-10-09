#!/usr/bin/env python3
#
# Script to produce a summary file of the contents of a data storage directory
# with information about the data contained inside.
#
# This code trawls through a specified directory and reads the headers of any
# PSRFITS or filterbank format files within it. It looks for the following
# information from each file:
# - Name
# - Path
# - Type
# - Size (GB)
# - Telescope
# - Observer
# - Project ID
# - Source
# - Observing mode
# - MJD
# - Center of frequency band (MHz)
#
# Example usage:
#
# > python make_readme.py -d /path/to/data/ -n survey_README.txt -g your_name
#
# Issues that could pop up:
# - The script intentionally ignores symlinks. It won't break; it will just ignore them.
# - It will only run on PSRFITS files and filterbank files.
# - It will break if it runs across a FITS file that is not PSRTFITS format.
#
# Things to do:
# - Add options to filter by frequency, MJD, source name, etc. You can already
#   filter by files by going into this code and editing the list of valid extensions,
#   but it would be nice to do that, and the other filters, on the command line.
#
# Technical note: The code reads PSRFITS files using the pdat module and filterbank
# files using sigpyproc, a python implementation of SIGPROC. This is for flexibility
# with different types of PSRFITS files, as well as dealing with some edge cases --
# for example, sigpyproc's reader for PSRFITS files only works on search mode data
# with the observing mode listed as "SEARCH". I know of a few instances where search
# mode data has its mode listed as "SRCH", which breaks sigpyproc but not pdat.
#
# All that said, this code will absolutely break on many other kinds of data! There
# are more weird cases I don't know about; I've written it specifically for the surveys
# I'm going through. Feel free to modify as needed.

import argparse
import datetime
import getpass
import glob
import os
import sys
import time

import pdat
from sigpyproc.readers import FilReader

parser = argparse.ArgumentParser(description='User inputs')
parser.add_argument('-d', help='Directory to search [Default: current working directory]', type=str)
parser.add_argument('-n', help='Name of output file [Default: "README.txt"]', type=str)
parser.add_argument('-l', help='Location of output file [Default: current working directory]', type=str)
parser.add_argument('-o', help='Owner of directory [Default: "Unknown"]', type=str)
parser.add_argument('-g', help='Person generating README [Default: "Unknown"]', type=str)
parser.add_argument('-v', help='Verbose option [Default: False]', type=bool)
args = parser.parse_args()

################################################################
# Use arguments and default values to change specific settings #
################################################################
if args.d:
    data_directory = args.d
else:
    data_directory = os.getcwd() + '/'
if args.n:
    output_name = args.n
else:
    output_name = 'README.txt'
if args.l:
    output_directory = args.l
else:
    output_directory = os.getcwd() + '/'
if args.o:
    owner = args.o
else:
    owner = 'Unknown'
if args.g:
    generator = args.g
else:
    # getpass finds your username. It should work on both Windows and Unix systems.
    generator = getpass.getuser()
if args.v:
    verbose = args.v
    if verbose not in [True, False]:
        print('-v must be True or False!')
        sys.exit()
else:
    verbose = False
    
def parse_data(data_file):
    """Reads header of file and grabs the information of interest.
    
    Inputs:
        data_file: PSRFITS or filterbank file to be read
    Outputs:
        path: path to file
        file: name of file
        ext: file extension
        size: size of file (GB)
        telescope: telescope
        observer: observer
        project_id: project code
        source: source being observed
        mode: observing mode
        MJD: MJD of observation
        center_freq: center of frequency band
        
    """
    
    path, file = os.path.split(data_file)
    name, ext = os.path.splitext(data_file)
    size = os.path.getsize(data_file) / 10**9 # GB
    
    if ext in ['.fits', '.sf', '.rf']:
        info = pdat.PyPSRFITS(data_file)
        header = info.hdr

        telescope = header['TELESCOP'].strip()
        observer = header['OBSERVER'].strip()
        project_id = header['PROJID'].strip()
        source = header['SRC_NAME'].strip()
        mode = header['OBS_MODE'].strip()
        MJD = header['STT_IMJD'] + header['STT_SMJD'] / (24*60*60)
        center_freq = header['OBSFREQ'] # MHz
    elif ext in ['.fil']:
        info = FilReader(data_file)
        header = info.header
        
        telescope = header.telescope.strip()
        observer = 'Unknown'
        project_id = 'Unknown'
        source = header.source.strip()
        mode = 'Unknown'
        MJD = header.tstart
        # FilReader's header doesn't provide an option for the central
        # frequency of the band, so you have to calculate that yourself.
        # Note that if fch1 is the highest frequency, header.foff (the
        # width of a channel) is negative.
        center_freq = header.fch1 + header.foff*(header.nchans - 1)/2
    
    return path, file, ext, size, telescope, observer, project_id, source, mode, MJD, center_freq
    
#############################################################
# Check whether relevant directories and output files exist #
#############################################################
if os.path.isdir(data_directory) == False:
    print('Data directory {} does not exist!'.format(data_directory))
    sys.exit()
if os.path.isdir(output_directory) == False:
    print('Output directory {} does not exist!'.format(output_directory))
    sys.exit()
if os.path.exists(os.path.join(output_directory, output_name)) == True:
    print('There is already a file named {}!'.format(os.path.join(output_directory, output_name)))
    sys.exit()

# See https://stackoverflow.com/a/13891070/6535830 and comments below; using
# .utcfromtimestamp() rather than .fromtimestamp() ensures you get the timestamp
# in UTC, rather than the system's local time.
start_time = time.time()
start_timestamp = datetime.datetime.utcfromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')

################################
# Pick files to search through #
################################
os.chdir(data_directory)

extensions = ['.fits', '.sf', '.rf', '.fil'] # need to add .fil, etc.

available_files = []
for e in extensions:
    available_files += glob.glob(os.path.abspath(data_directory) + '/**/*{}'.format(e), recursive=True)

# 1000 files honestly isn't that much, but I wanted to set a fairly low threshold to err
# on the side of caution. Realistically, if you're dealing with a couple orders of magnitude
# more than this, you're probably trawling through an upper-level directory of a data
# storage machine, which is hopefully a once-in-a-long-while thing.
if len(available_files) > 10**3:
    result = input(
        'There are {} files to read. Are you sure you want to proceed? [Y/N] '.format(len(available_files)))
    if result != 'Y':
        sys.exit()

###############################################
# Set up lists to hold quantities of interest #
###############################################
n_files = 0
tot_size = 0
exts = []
telescopes = []
observers = []
project_ids = []
sources = []
modes = []
MJDs = []
center_freqs = []

######################################
# Go through desired files to search #
######################################
for af in available_files:
    if os.path.islink(af) == False:
        if verbose == True:
            print('Reading header of {}.'.format(af))
        path, file, ext, size, telescope, observer, project_id, source, mode, MJD, center_freq = parse_data(af)
        n_files += 1
        tot_size += size
        if ext not in exts:
            exts.append(ext)
        if telescope not in telescopes:
            telescopes.append(telescope)
        if observer not in observers:
            observers.append(observer)
        if project_id not in project_ids:
            project_ids.append(project_id)
        if source not in sources:
            sources.append(source)
        if mode not in modes:
            modes.append(mode)
        if MJD not in MJDs:
            MJDs.append(MJD)
        if center_freq not in center_freqs:
            center_freqs.append(center_freq)
    else:
        if verbose == True:
            print('{} is a symlink and will not be read.'.format(af))
            
# Creates a version of the center frequencies as strings
# to make it easier to list them in the README.
string_center_freqs = [str(freq) for freq in center_freqs]
        
# I get seperate timestamps for starting and ending times for the edge case
# where this is being run on a ton of files and a couple happen to be moved,
# modified or deleted in the interim.
end_time = time.time()
end_timestamp = datetime.datetime.utcfromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')

############################################################################
# Write information to output file. This also creates a field for the user #
# to manually add notes afterwards, although I intend for the output file  #
# to be manually modified later anyway if needed.                          #
############################################################################
os.chdir(output_directory)

output_file = open(output_name, 'w')
output_file.write('README file for {} generated by {}.\n'.format(data_directory, __file__))
output_file.write('Owner: {}\n'.format(owner))
output_file.write('Generated by: {}\n'.format(generator))
output_file.write('Started at {}; completed at {}.\n'.format(start_timestamp, end_timestamp))
output_file.write('Number of files: {}\n'.format(n_files))
output_file.write('Total size (GB): {:.2f}\n'.format(tot_size))
output_file.write('File types: {}\n'.format(', '.join(sorted(exts))))
output_file.write('Telescope: {}\n'.format(', '.join(sorted(telescopes))))
output_file.write('Observers: {}\n'.format(', '.join(sorted(observers))))
output_file.write('Project IDs: {}\n'.format(', '.join(sorted(project_ids))))
output_file.write('Sources: {}\n'.format(', '.join(sorted(sources))))
output_file.write('Modes: {}\n'.format(', '.join(sorted(modes))))
output_file.write('Center frequencies (MHz): {}\n'.format(', '.join(sorted(string_center_freqs))))
output_file.write('\n')
output_file.write('Notes:')
output_file.close()
