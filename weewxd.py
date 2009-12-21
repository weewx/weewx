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

If you wish to use a different engine than the default, 
then subclass the default engine "StdEngine" and specify that class in
the call to the main entry point as parameter 'EngineClass'.

See the document "customizing.htm" for details.
"""

import weewx.wxengine

# Enter the main loop. 
weewx.wxengine.main()
