#!/usr/bin/env python
#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Transfer from sqlite to MySQL database or vv. Adjust parameters as necessary."""
from __future__ import with_statement
from weewx.manager import Manager
import schemas.wview

old_archive_dict = {'driver'        : 'weedb.sqlite',
                    'database_name' : '/home/weewx/archive/weewx.sdb'}

new_archive_dict = {'driver'        : 'weedb.mysql',
                    'database_name' : 'weewx',
                    'host'          : 'localhost',
                    'user'          : 'weewx',
                    'password'      : 'weewx'}

with Manager.open(old_archive_dict) as old_archive:
    with Manager.open_with_create(new_archive_dict, schema=schemas.wview.schema) as new_archive:

        # This is very fast because it is done in a single transaction context:
        new_archive.addRecord(old_archive.genBatchRecords())
