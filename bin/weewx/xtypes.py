#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined, extended types"""

import weewx

#
# List of type extensions. Each should be a function, with the calling signature
#   fn(key, record, db_manager)
# where
#   key is the observation type to be calculated(e.g., 'dewpoint');
#   record is a dictionary holding the observation data;
#   db_manager is an open instance of weewx.manager.Manager.
#
scalar_types = []


def get_scalar(key, record, db_manager=None):
    """Search the list, looking for the key 'key'."""
    for xtype in scalar_types:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype(key, record, db_manager)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(key)
