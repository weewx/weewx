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
then subclass the default engine and specify that in
the call to the main entry point. 

For example, say you wanted to print out every loop packet. 
One way to do this would be as follows:

  # Create a specialized, custom engine:
  class MyEngine(weewx.wxengine.StdEngine):

      # Pass on the init parameters to my superclass
      def __init__(self, *args, **vargs):
          super(MyEngine, self).__init__(*args, **vargs)
      
      # Override the member function that processes loop packets:
      def processLoopPacket(self, physicalPacket):
          # First let the superclass process it:
          super(MyEngine, self).processLoopPacket(physicalPacket)
          # Then add my specialized processing:
          print "Hi! I'm a specialized loop packet processor that prints out the packet:\n", physicalPacket

  # Specify that my specialized engine should be used instead
  # of the default:
  
  weewx.wxengine.main(EngineClass=MyEngine)
  
An alternative approach is to define a new service. For an example
of a new service, see the alarm example in the example subdirectory.
In this case, the new service needs to be included in the service_list.

For an example, to include the example alarm service, the call into the
main function would look like:

  weewx.wxengine.main(service_list = ['weewx.wxengine.StdWunderground',
                                      'weewx.wxengine.StdCatchUp',
                                      'weewx.wxengine.StdTimeSynch',
                                      'weewx.wxengine.StdPrint',
                                      'examples.alarm.MyAlarm',
                                      'weewx.wxengine.StdProcess'])
"""

import weewx.wxengine

# Enter the main loop. 

weewx.wxengine.main(service_list = ['weewx.wxengine.StdWunderground',
                                    'weewx.wxengine.StdCatchUp',
                                    'weewx.wxengine.StdTimeSynch',
                                    'weewx.wxengine.StdPrint',
                                    'examples.alarm.MyAlarm',
                                    'weewx.wxengine.StdProcess'])
