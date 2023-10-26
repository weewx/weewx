#
#    Copyright (c) 2009-2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Weather-specific database manager."""

import weewx.manager


class WXDaySummaryManager(weewx.manager.DaySummaryManager):
    """Daily summaries, suitable for WX applications.
    
    OBSOLETE. Provided for backwards compatibility.
    
    """
