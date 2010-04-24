#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Example of how to extend the weewx engine.

In this example, we create a new event "firstArchiveOfDay".
It will be called when the first archive record of a new 
day arrives. 
"""

from weewx.wxengine import StdEngine, StdService
from weeutil.weeutil import startOfArchiveDay

class MyEngine(StdEngine):
    """A customized weewx engine."""
    
    def __init__(self, *args, **vargs):
        # Pass on the initialization data to my superclass:
        StdEngine.__init__(self, *args, **vargs)
        
        # This will record the timestamp of the old day
        self.old_day = None
        
    def newArchivePacket(self, rec):
        # First let my superclass process it:
        StdEngine.newArchivePacket(self, rec)
        
        # Get the timestamp of the start of the day using
        # the utility function startOfArchiveDay 
        dayStart_ts = startOfArchiveDay(rec['dateTime'])

        # Call the function newDay() if either this is
        # the first archive since startup, or if a new day has started
        if not self.old_day or self.old_day != dayStart_ts:
            self.old_day = dayStart_ts
            self.newDay(rec)                          # NOTE 1
            
    def newDay(self, rec):
        """Called when the first archive record of a day arrives."""
        
        # Go through the list of service objects. This
        # list is actually in my superclass StdEngine.
        for svc_obj in self.service_obj:
            # Because this is a new event, not all services will
            # be prepared to accept it. Be prepared for an AttributeError
            # exception:
            try:                                     # NOTE 2
                svc_obj.firstArchiveOfDay(rec)
            except AttributeError:
                pass

# Define a new service to take advantage of the new event
class DailyService(StdService):
    """This service can do something when the first archive record of
    a day arrives."""
    
    def firstArchiveOfDay(self, rec):
        """Called when the first archive record of a day arrives."""
        
        print "The first archive of the day has arrived!"
        print rec
        
        # You might want to do something here like run a cron job
