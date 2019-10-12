#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined, extended types"""
from __future__ import print_function

import weewx

scalar_types = []


def get_scalar(key, record, db_manager=None):
    for xtype in scalar_types:
        try:
            return xtype(key, record, db_manager)
        except weewx.UnknownType:
            pass
    raise weewx.UnknownType(key)
