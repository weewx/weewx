#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined, extensible scalars.

Scalar type extensions use a function with signature

    fn(obs_type, record, db_manager)

where

- `obs_type` is the type to be computed.
- `record` is a WeeWX record. It will include at least types `dateTime` and `usUnits`.
- `db_manager` is an instance of `weewx.manager.Manager`, or a subclass. The connection will be open and usable.

The function should return:

- A single scalar, possibly `None`, of type `obs_type`.

The function should raise:

- An exception of type `weewx.UnknownType`, if the type `obs_type` is unknown to the function.
- An exception of type `weewx.CannotCalculate` if the type is known to the function, but all the information
necessary to calculate the type is not there.
"""

import weewx

scalar_types = []


def get_scalar(obs_type, record, db_manager=None):
    """Search the list, looking for the key 'obs_type'."""
    for xtype in scalar_types:
        try:
            # Try this function. It will raise an exception if it does not know about the type.
            return xtype(obs_type, record, db_manager)
        except weewx.UnknownType:
            # This function does not know about the type. Move on to the next one.
            pass
    # None of the functions worked.
    raise weewx.UnknownType(obs_type)

