#!/usr/bin/env python
#
#    Copyright (c) 2009, 2010, 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Entry point to the weewx weather system."""

# First import any user extensions:
import user.extensions       #@UnusedImport
# Now the engine
import weewx.wxengine

# Enter the main loop. This call will use the default
# engine, StdEngine, but this can be overridden with
# keyword EngineClass. E.g.,
#
# weewx.wxengine.main(EngineClass = MyEngine)
#
weewx.wxengine.main()
