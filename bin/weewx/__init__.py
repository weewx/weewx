#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Package weewx. A set of modules for supporting a weather station on a sqlite database.

"""
import time

__version__="1.9.0"

# Holds the program launch time in unix epoch seconds:
# Useful for calculating 'uptime.'
launchtime_ts = time.time()

# Set to true for extra debug information:
debug = False

# Exit return codes
CMD_ERROR    = 2
CONFIG_ERROR = 3
IO_ERROR     = 4

# Constants used to indicate a unit system:
US     = 1
METRIC = 2

#
# Define possible exceptions that could get thrown.
#
class WeeWxIOError(IOError):
    """Base class of exceptions thrown when encountering an I/O error with the console."""

class WakeupError(WeeWxIOError):
    """Exception thrown when unable to wake up the console"""
    
class AckError(WeeWxIOError):
    """Exception thrown when unable to get an acknowledging <ACK> from the console."""
    
class CRCError(WeeWxIOError):
    """Exception thrown when unable to pass a CRC check."""

class RetriesExceeded(WeeWxIOError):
    """Exception thrown when max retries exceeded."""

class UnknownArchiveType(StandardError):
    """Exception thrown after reading an unrecognized archive type."""

class UnsupportedFeature(StandardError):
    """Exception thrown when attempting to access a feature that is not supported (yet)."""
    
class ViolatedPrecondition(StandardError):
    """Exception thrown when a function is called with violated preconditions."""
    
class LogicError(StandardError):
    """Exception thrown when there is an internal logic error in the code."""
