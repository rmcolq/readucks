"""
Copyright 2019 Andrew Rambaut (a.rambaut@ed.ac.uk)
https://github.com/rambaut/readucks

This module contains the main script for Readucks. It is executed when a user runs `readucks`
(after installation) or `readucks-runner.py` (directly from the source directory).

This file is part of Readucks. Readucks is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Readucks is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Readucks. If
not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

from Bio import SeqIO
import parasail

from .demuxer import demux_read, print_alignment
from .barcodes import NATIVE_BARCODES, PCR_BARCODES, RAPID_BARCODES
from .misc import bold_underline, MyHelpFormatter, output_progress_line
from .version import __version__

def main():
    '''
    Entry point for Readucks. Gets arguments, processes them and then calls process_files function
    to do the actual work.
    :return:
    '''
    args = get_arguments()

    barcode_set = 'native'
    if args.native_barcodes:
        barcode_set = 'native'
    if args.pcr_barcodes:
        barcode_set = 'pcr'
    if args.rapid_barcodes:
        barcode_set = 'rapid'


    process_files(args.input_path, args.output, barcode_set, args.limit_barcodes_to, args.single, args.threshold / 100.0, args.secondary_threshold / 100.0, args.verbosity)


def process_files(input_path, output_path, barcode_set, limit_barcodes_to, single_barcode, threshold, secondary_threshold, verbosity):
    """
    Core function to process one or more input files and create the required output files.

    Iterates through the reads in one or more input files and bins or filters them into the
    output files as required.
    """

    start_time = datetime.now()

    read_files = get_input_files(input_path)

    output_file = open(output_path, 'wt')

    if verbosity > 0:
        print(bold_underline('\n' + str(len(read_files)) + ' read files found'), flush=True)

    if verbosity > 1:
        print(bold_underline('\nRead files found:'), flush=True)
        for read_file in read_files:
            print(read_file, flush=True)

    output_progress_line(0, len(read_files))

    barcode_counts = defaultdict(int)

    if barcode_set == 'native':
        barcodes = NATIVE_BARCODES
    elif barcode_set == 'pcr':
        barcodes = PCR_BARCODES
    elif barcode_set == 'rapid':
        barcodes = RAPID_BARCODES
    else:
        sys.exit(
            'Unrecognised barcode_set: ' + barcode_set)

    #todo - limit set of barcodes

    print('name', 'barcode',
          'primary_barcode', 'primary_is_start', 'primary_score', 'primary_identity', 'primary_matches', 'primary_length',
          'secondary_barcode', 'secondary_is_start', 'secondary_score', 'secondary_identity', 'secondary_matches', 'secondary_length',
          file = output_file, sep = '\t')
    
    for index, read_file in enumerate(read_files):
        process_read_file(read_file, output_file, barcodes, single_barcode, threshold, secondary_threshold, barcode_counts, verbosity)

        output_progress_line(index, len(read_files))

    output_progress_line(len(read_files), len(read_files))

    output_file.close()

    time = datetime.now() - start_time

    if verbosity > 0:
        print("\n\nTime taken: " + str(time.total_seconds()) + " secs")

    if verbosity > 0:
        print(bold_underline('\nBarcodes called:'), flush=True)
        barcode_names = []
        for barcode_id in barcode_counts:
            barcode_names.append(barcode_id)

        barcode_names.sort()

        for barcode_name in barcode_names:
            print(barcode_name + ": " + str(barcode_counts[barcode_name]), flush=True)



def get_input_files(input_path):
    '''
    Takes a path to a single file or a directory and returns a list of file paths to be processed.
    :param input_file_or_directory: The input path
    :param verbosity: Verbosity level to report
    :param print_dest: Where to report (stdout or stderr)
    :return: An array of file paths to process
    '''
    input_files = []

    if os.path.isfile(input_path):
        input_files.append(input_path)

    # If the input is a directory, search it recursively for fastq files.
    elif os.path.isdir(input_path):
        input_files = sorted([os.path.join(dir_path, f)
                              for dir_path, _, filenames in os.walk(input_path)
                              for f in filenames
                              if f.lower().endswith('.fastq') or f.lower().endswith('.fastq.gz') or
                              f.lower().endswith('.fasta') or f.lower().endswith('.fasta.gz')])
        if not input_files:
            sys.exit('Error: could not find FASTQ/FASTA files in ' + input_path)

    else:
        sys.exit('Error: could not find ' + input_path)

    return input_files


def process_read_file(read_file, output_file, barcodes, single_barcode, threshold, secondary_threshold, barcode_counts, verbosity):
    """
    Iterates through the reads in an input files and bins or filters them into the
    output files as required.
    """

    nuc_matrix = parasail.matrix_create("ACGT", 2, -1)

    for read in SeqIO.parse(read_file, "fastq"):

        result = demux_read(read, barcodes, single_barcode, threshold, secondary_threshold, 3, 1, nuc_matrix, verbosity > 1)

        barcode_counts[result['call']] += 1

        print(result['name'], result['call'],
              result['primary']['id'], result['primary']['start'], result['primary']['score'], result['primary']['identity'], result['primary']['matches'], result['primary']['length'],
              result['secondary']['id'], result['primary']['start'], result['secondary']['score'], result['secondary']['identity'], result['secondary']['matches'], result['secondary']['length'],
              file = output_file, sep = '\t')

        if verbosity > 1:
            print_alignment(result)


def get_arguments():
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(description='Readucks: a simple demuxing tool for nanopore data.',
                                     formatter_class=MyHelpFormatter, add_help=False)

    main_group = parser.add_argument_group('Main options')
    main_group.add_argument('-i', '--input', dest='input_path', required=True,
                            help='FASTQ of input reads or a directory which will be '
                                 'recursively searched for FASTQ files (required).')
    main_group.add_argument('-o', '--output', required=True,
                            help='Output filename (or filename prefix)')
    main_group.add_argument('-v', '--verbosity', type=int, default=1,
                            help='Level of output information: 0 = none, 1 = some, 2 = lots')

    barcode_group = parser.add_argument_group('Demuxing options')
    barcode_group.add_argument('--single', action='store_true',
                               help='Only attempts to match a single barcode at one end (default double)')
    barcode_group.add_argument('--native_barcodes', action='store_true',
                               help='Only attempts to match the 24 native barcodes (default)')
    barcode_group.add_argument('--pcr_barcodes', action='store_true',
                               help='Only attempts to match the 96 PCR barcodes')
    barcode_group.add_argument('--rapid_barcodes', action='store_true',
                               help='Only attempts to match the 12 rapid barcodes')
    barcode_group.add_argument('--limit_barcodes_to', nargs='+', type=int, required=False,
                               help='Specify a list of barcodes to look for (numbers refer to native, PCR or rapid)')
    # barcode_group.add_argument('--custom_barcodes',
    #                            help='CSV file containing custom barcode sequences')
    barcode_group.add_argument('--threshold', type=float, default=90.0,
                               help='A read must have at least this percent identity to a barcode')
    barcode_group.add_argument('--secondary_threshold', type=float, default=70.0,
                               help='The second barcode must have at least this percent identity (and match the first one)')

    help_args = parser.add_argument_group('Help')
    help_args.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                           help='Show this help message and exit')
    help_args.add_argument('--version', action='version', version=__version__,
                           help="Show program's version number and exit")

    args = parser.parse_args()

    if (args.native_barcodes and args.pcr_barcodes) or (args.native_barcodes and args.rapid_barcodes) or (args.pcr_barcodes and args.rapid_barcodes):
        sys.exit(
            'Error: only one of the following options may be used: --native_barcodes, --pcr_barcodes or --rapid_barcodes')

    if (args.single and args.secondary_threshold):
        sys.exit(
            'Error: the option --secondary_threshold is not available with --single')

    if (args.threshold > 0.0 and args.threshold < 1.0 or
            args.secondary_threshold > 0.0 and args.secondary_threshold < 1.0):
        sys.exit(
            'Error: the options --threshold and --secondary_threshold should be given as percentages')

    return args

