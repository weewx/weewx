#!/usr/bin/env python
# $Id$
# Copyright (c) 2009-2013 Tom Keffer <tkeffer@gmail.com>
"""weewx configuration file upgrade script.  Use this script to merge new
   features into an existing configuration file.  The script takes an 
   installation directory and two configuration files as input then outputs
   the merged contents of the input files.

   The weewx setup.py script must be in the same directory as this script."""

import optparse
import os
import shutil
import tempfile

import configobj

import setup

description = """merge weewx configuration file"""
usage = """%prog --install-dir dir --a file --b file --c file"""

def main():
    parser = optparse.OptionParser(description=description, usage=usage)

    parser.add_option('--version', dest='version', action='store_true',
                      help='display version then exit')
    parser.add_option('--install-dir', dest='idir', type=str, metavar='DIR',
                      help='installation directory DIR')
    parser.add_option('--a', dest='filea', type=str, metavar='FILE',
                      help='first file FILE')
    parser.add_option('--b', dest='fileb', type=str, metavar='FILE',
                      help='second file FILE')
    parser.add_option('--c', dest='filec', type=str, metavar='FILE',
                      help='merged file FILE')
    parser.add_option('--debug', dest='debug', action='store_true',
                      help='display contents of merged file to stdout')

    (options, _args) = parser.parse_args()
    if options.version:
        print setup.get_version()
        exit(0)

    errmsg = []
    if options.idir is None:
        errmsg.append('no installation directory specified')
    if options.filea is None:
        errmsg.append('no first filename specified')
    if options.fileb is None:
        errmsg.append('no second filename specified')
    if options.filec is None:
        errmsg.append('no merged filename specified')
    if len(errmsg) > 0:
        print '\n'.join(errmsg)
        exit(1)

    merged_cfg = setup.merge_config_files(options.filea, options.fileb,
                                          options.idir)

    if options.debug:
        printdict(merged_cfg)
    else:
        tmpfile = tempfile.NamedTemporaryFile("w", 1)
        merged_cfg.write(tmpfile)
        if os.path.exists(options.filec):
            _bup_cfg = setup.save_path(options.filec)
        shutil.copyfile(tmpfile.name, options.filec)

def printdict(d, indent=0):
    for k in d.keys():
        if type(d[k]) is configobj.Section:
            for _i in range(indent):
                print ' ',
            print k
            printdict(d[k], indent=indent+1)
        else:
            for _i in range(indent):
                print ' ',
            print k, '=', d[k]

if __name__ == "__main__":
    main()

