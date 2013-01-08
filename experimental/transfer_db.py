#!/usr/bin/env python
#
#    Copyright (c) 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Transfer from sqlite to MySQL database or vv. Adjust parameters as necessary."""
from weewx.archive import Archive
from user.schemas import defaultArchiveSchema

old_archive_dict = {'driver' : 'weedb.sqlite',
                    'database' : '/home/weewx/archive/weewx.sdb'}

new_archive_dict = {'driver' : 'weedb.mysql',
                    'database' : 'weewx',
                    'host'     : 'localhost',
                    'user'     : 'weewx',
                    'password' : 'weewx'}

with Archive.open(old_archive_dict) as old_archive:
    with Archive.open_with_create(new_archive_dict, defaultArchiveSchema) as new_archive:

        # This is very fast because it is done in a single transaction context:
        new_archive.addRecord(old_archive.genBatchRecords())
