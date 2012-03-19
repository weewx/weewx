#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Event class"""

#===============================================================================
#                       Possible event types.
#===============================================================================
#
# These could be constants, but classes are much easier to debug.
#
class STARTUP(object):
    pass
class PRE_LOOP(object):
    pass
class NEW_LOOP_PACKET(object):
    pass
class ARCHIVE_RECORD_DUE(object):
    pass
class NEW_ARCHIVE_RECORD(object):
    pass
class CATCHUP_ARCHIVE(object):
    pass
#class START_LOOP(object):
#    pass
class END_LOOP(object):
    pass

#===============================================================================
#                       Class Event
#===============================================================================
class Event(object):
    """Represents an event."""
    def __init__(self, event_type, **argv):
        self.event_type = event_type

        for key in argv:
            setattr(self, key, argv[key])

