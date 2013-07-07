#
#    Copyright (c) 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
"""Special service for publishing to the Weather Underground's RapidFire protocol.

This version is experimental and only works with the Davis Vantage instruments.
"""
import Queue
import datetime
import httplib
import socket
import syslog
import threading
import urllib
import urllib2

import weewx.wxengine
import weewx.restful

class StdRapidFire(weewx.wxengine.StdService):
    """Adds the ability to post to the Weather Underground's RapidFire facility"""

    def __init__(self, engine, config_dict):
        super(StdRapidFire, self).__init__(engine, config_dict)
        
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

        # Loop packets will be pushed on to this queue:
        self.rapidfire_queue = Queue.Queue()
        
        # Start up a thread for the RapidFire:
        self.rapidfire_thread = RapidFire(self.rapidfire_queue, **config_dict['RapidFire'])
        self.rapidfire_thread.start()
        syslog.syslog(syslog.LOG_DEBUG, "rapidfire: Started RapidFire thread.")
        
    def new_loop_packet(self, event):
        # Push the new packet on to the queue:
        self.rapidfire_queue.put(event.packet)
        
    def shutDown(self):
        """Shut down the RapidFire thread"""

        # Put a None in the queue. This will signal the thread to shutdown
        self.rapidfire_queue.put(None)
        # Wait up to 20 seconds for the thread to exit:
        self.rapidfire_thread.join(20.0)
        if self.rapidfire_thread.isAlive():
            syslog.syslog(syslog.LOG_ERR, "rapidfire: Unable to shut down RapidFire thread")
        else:
            syslog.syslog(syslog.LOG_DEBUG, "rapidfire: Shut down RapidFire thread.")
        
class RapidFire(threading.Thread):
    """Dedicated thread for publishing weather data using the WU RapidFire protocol
    
    Inherits from threading.Thread.

    Basically, it watches a queue, and if a packet appears in it, it publishes it.
    """

    def __init__(self, rapidfire_queue, **rf_dict):
        threading.Thread.__init__(self, name="RapidFireThread")

        self.rapidfire_queue = rapidfire_queue
        self.station  = rf_dict['station']
        self.password = rf_dict['password']
        self.timeout  = int(rf_dict.get('timeout', 5))
        
        # In the strange vocabulary of Python, declaring yourself a "daemon thread"
        # allows the program to exit even if this thread is running:
        self.setDaemon(True)

    def run(self):

        while True :
            # This will block until something appears in the queue:
            packet = self.rapidfire_queue.get()

            # If packets have backed up in the queue, throw them all away except the last one.
            while self.rapidfire_queue.qsize():
                packet = self.rapidfire_queue.get()
                
            # A 'None' value appearing in the queue is our signal to exit
            if packet is None:
                break
        
            # Form the URL from the information in the packet    
            url = self.getURL(packet)

            # Now post it
            self.postURL(url)

    def getURL(self, packet):
        """Return an URL for posting using the RF protocol"""
    
        _liststr = ["action=updateraw", "ID=%s" % self.station, "PASSWORD=%s" % self.password ]
        
        # Go through each of the supported types, formatting it, then adding to _liststr:
        for _key in weewx.restful.Ambient._formats:
            v = packet.get(_key)
            # Check to make sure the type is not null
            if v is not None :
                if _key == 'dateTime':
                    # For dates, convert from time stamp to a string, using what
                    # the Weather Underground calls "MySQL format." I've fiddled
                    # with formatting, and it seems that escaping the colons helps
                    # its reliability. But, I could be imagining things.
                    v = urllib.quote(datetime.datetime.utcfromtimestamp(v).isoformat('+'), '-+')
                # Format the value, and accumulate in _liststr:
                _liststr.append(weewx.restful.Ambient._formats[_key] % v)
        # Add the realtime flag ...
        _liststr.append("realtime=1")
        # ... and the update frequency ...
        _liststr.append("rtfreq=2.5")
        # ... and the software type and version:
        _liststr.append("softwaretype=weewx-%s" % weewx.__version__)
        # Now stick all the little pieces together with an ampersand between them:
        _urlquery='&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url="http://rtupdate.wunderground.com/weatherstation/updateweatherstation.php?" + _urlquery
        return _url
    
    def postURL(self, url):
        """Post the given url to the Weather Underground's RapidFire site."""
        try:
            _response = urllib2.urlopen(url, timeout=self.timeout)
        except (urllib2.URLError, socket.error, httplib.BadStatusLine), e:
            # Unsuccessful. Log it
            syslog.syslog(syslog.LOG_DEBUG, "rapidfire: Failed RF upload. Reason: %s" % (e,))
        else:
            # No exception thrown, but we're still not done.
            # We have to also check for a bad station ID or password.
            # It will have the error encoded in the return message:
            for line in _response:
                # PWSweather signals with 'ERROR', WU with 'INVALID':
                if line.startswith('ERROR') or line.startswith('INVALID'):
                    # Bad login. No reason to retry. Log it and raise an exception.
                    syslog.syslog(syslog.LOG_ERR, "rapidfire: WU returns %s. Aborting." % (line,))
                    raise weewx.restful.FailedPost, line

        # Does not seem to be an error. We're done.
        return
    
