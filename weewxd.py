#!/usr/bin/env python
#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

"""weewxd.py

Entry point to the weewx weather system.
"""

import weewx.wxengine

# Enter the main loop:
weewx.wxengine.main()
