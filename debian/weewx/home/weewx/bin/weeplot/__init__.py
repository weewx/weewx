#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 233 $
#    $Author: tkeffer $
#    $Date: 2010-04-12 15:41:45 -0700 (Mon, 12 Apr 2010) $
#
"""Package weeplot. A set of modules for doing simple plots

"""
# Define possible exceptions that could get thrown.

class ViolatedPrecondition(StandardError):
    """Exception thrown when a function is called with violated preconditions.
    
    """
