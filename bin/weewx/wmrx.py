#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Classes and functions for interfacing with an Oregon Scientific WMR100 (WMR100N) station

    The following references were useful for figuring out the WMR protocol:
    
    From Per Ejeklint:
        https://github.com/ejeklint/WLoggerDaemon/blob/master/Station_protocol.md
        
    From Rainer Finkeldeh:
        http://www.bashewa.com/wmr200-protocol.php
        
    The WMR driver for the wfrog weather system:
        http://code.google.com/p/wfrog/source/browse/trunk/wfdriver/station/wmr200.py
        
    Unfortunately, there is no documentation for PyUSB v0.4, so you have to back it out of the
    source code, available at:
        https://pyusb.svn.sourceforge.net/svnroot/pyusb/branches/0.4/pyusb.c
    
"""

import time
import operator
import syslog

import usb

import weeutil.weeutil
import weewx.abstractstation
import weewx.units
import weewx.wxformulas

class WMR100(weewx.abstractstation.AbstractStation):
    
    def __init__(self, **stn_dict) :
        """Initialize an object of type WMR100.
        
        NAMED ARGUMENTS:
        
        altitude: A 2-way tuple. First element is altitude, second element is the unit
        it is in. Example: (700, 'foot'). Required.
        
        timeout: How long to wait, in seconds, before giving up on a response from the
        USB port. [Optional. Default is 15 seconds]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 5 seconds]

        max_tries: How many times to try before giving up. [Optional.
        Default is 3]
        
        vendor_id: The USB vendor ID for the WMR [Optional. Default is 0xfde.
        
        product_id: The USB product ID for the WM [Optional. Default is 0xca01.
        
        interface: The USB interface [Optional. Default is 1]
        
        IN_endpoint: The IN USB endpoint used by the WMR. [Optional. Default is usb.ENDPOINT_IN + 1]
        """
        
        altitude_t           = weeutil.weeutil.option_as_list(stn_dict['altitude'])
        # Form a value-tuple:
        altitude_vt = (float(altitude_t[0]), altitude_t[1], "group_altitude")
        # Now perform the conversion, extracting only the value:
        self.altitude          = weewx.units.convert(altitude_vt, 'meter').value
        self.timeout           = float(stn_dict.get('timeout', 15.0))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 5.0))
        self.max_tries         = int(stn_dict.get('max_tries', 3))
        self.vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        self.product_id        = int(stn_dict.get('product_id', '0xca01'), 0)
        self.interface         = int(stn_dict.get('interface', 0))
        self.IN_endpoint       = int(stn_dict.get('IN_endpoint', usb.ENDPOINT_IN + 1))

        self.lastRainTotal = None
        self.openPort()

    def openPort(self):
        dev = self._findDevice()
        if not dev:
            syslog.syslog(syslog.LOG_ERR, "wmrx: Unable to find USB device (0x%04x, 0x%04x)" % (self.vendor_id, self.product_id))
            raise weewx.WeeWxIOError("Unable to find USB device")
        self.devh = dev.open()
        # Detach any old claimed interfaces
        try:
            self.devh.detachKernelDriver(self.interface)
        except:
            pass
        try:
            self.devh.claimInterface(self.interface)
        except usb.USBError, e:
            self.closePort()
            syslog.syslog(syslog.LOG_CRIT, "wmrx: Unable to claim USB interface. Reason: %s" % e)
            raise weewx.WeeWxIOError(e)
        
    def closePort(self):
        try:
            self.devh.releaseInterface()
        except:
            pass
        try:
            self.devh.detachKernelDriver(self.interface)
        except:
            pass
        
    def genLoopPackets(self):
        """Generator function that continuously returns loop packets"""
        
        while True:
            for _packet in self.genPackets():
                _packet_type = _packet[1]
                print "packet: ", len(_packet)*" 0x%x" % tuple(_packet)
                if _packet_type in WMR100._dispatch_dict:
                    _record = WMR100._dispatch_dict[_packet_type](self, _packet)
                    if _record is not None : 
                        yield _record
                
    def genPackets(self):
        """Generate measurement packets. These are 8 to 17 byte long packets containing
        the raw measurement data.
        
        For a pretty good summary of what's in these packets see
        https://github.com/ejeklint/WLoggerDaemon/blob/master/Station_protocol.md
        """
        
        # Wrap the byte generator function in GenWithPeek so we 
        # can peek at the next byte in the stream. The result, the variable
        # genBytes, will be a generator function.
        genBytes = weeutil.weeutil.GenWithPeek(self._genBytes_raw())

        # Start by throwing away any partial packets:
        for ibyte in genBytes:
            if genBytes.peek()!=0xff:
                break
        
        buff = []
        # March through the bytes generated by the generator function genBytes:
        for ibyte in genBytes:
            # If both this byte and the next one are 0xff, then we are at the end of a record
            if ibyte==0xff and genBytes.peek()==0xff:
                # We are at the end of a packet.
                # Compute its checksum. This can throw an exception if the packet is empty.
                try:
                    computed_checksum = reduce(operator.iadd, buff[:-2])
                except TypeError, e:
                    if weewx.debug:
                        syslog.syslog(syslog.LOG_DEBUG, "wmrx: Exception while calculating checksum.")
                        syslog.syslog(syslog.LOG_DEBUG, "****  %s" % e)
                else:
                    actual_checksum   = (buff[-1] << 8) + buff[-2]
                    if computed_checksum == actual_checksum:
                        # Looks good. Yield the packet
                        yield buff
                    elif weewx.debug:
                        syslog.syslog(syslog.LOG_DEBUG, "wmrx: Bad checksum on buffer of length %d" % len(buff))
                # Throw away the next character (which will be 0xff):
                genBytes.next()
                # Start with a fresh buffer
                buff = []
            else:
                buff.append(ibyte)
             
    #===============================================================================
    #                         USB functions
    #===============================================================================
             
                               
    def _findDevice(self):
        """Find the given vendor and product IDs on the USB bus"""
        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.vendor_id and dev.idProduct == self.product_id:
                    return dev

    def _genBytes_raw(self):
        """Generates a sequence of bytes from the WMR USB reports."""
        
        # Only need to be sent after a reset or power failure of the station:
        self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,       # requestType
                             0x0000009,                                  # request
                             [0x20,0x00,0x08,0x01,0x00,0x00,0x00,0x00],  # buffer
                             0x0000200,                                  # value
                             0x0000000,                                  # index
                             1000)                                       # timeout
            
        nerrors=0
        while True:
            # Continually loop, retrieving "USB reports". They are 8 bytes long each.
            report = self.devh.interruptRead(self.IN_endpoint,
                                             8, # bytes to read
                                             int(self.timeout*1000))
            print report
            try:
                # While the report is 8 bytes long, only a smaller, variable portion of it
                # has measurement data. This amount is given by byte zero:
                nbytes = report[0]
                # Index of the first good byte:
                i = 1
                while nbytes:
                    yield report[i]
                    i      += 1     # Advance to the next index
                    nbytes -= 1     # Decrement the number of bytes left in this report
                nerrors=0
            except (IndexError, usb.USBError), e:
                syslog.syslog(syslog.LOG_DEBUG, "wmrx: Bad USB report received.")
                syslog.syslog(syslog.LOG_DEBUG, "***** %s" % e)
                nerrors += 1
                if nerrors>self.max_tries:
                    syslog.syslog(syslog.LOG_ERR, "wmrx: Max retries exceeded while fetching USB reports")
                    raise weewx.WeeWxIOError("Max retries exceeded while fetching USB reports")
                time.sleep(self.wait_before_retry)
    
    #===============================================================================
    #                         LOOP packet decoding functions
    #===============================================================================

    def _rain_packet(self, packet):
        rainTotal = ((packet[9] << 8) + packet[8]) / 10.0
        if self.lastRainTotal is not None:
            rain = rainTotal - self.lastRainTotal
        else:
            rain = None
        self.lastRainTotal = rainTotal
        _record = {'rainRate'    : ((packet[3] << 8) + packet[2]) / 10.0,
                   'rain'        : rain,
                   'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.US}
        return _record


    def _temperature_packet(self, packet):
        _record = {'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        T = ((packet[4] << 8) + packet[3])/10.0
        D = ((packet[4] << 8) + packet[3])/10.0
        R = float(packet[5])
        channel = packet[2] & 0x0f
        if channel == 0:
            _record['inTemp']      = T
            _record['inHumidity']  = R
        elif channel == 1:
            _record['outTemp']     = T
            _record['dewpoint']    = D
            _record['outHumidity'] = R
        elif channel == 2:
            _record['extraTemp1']  = T
            _record['extraHumid1'] = R

        # Does this packet include a wind chill?
        if packet[8] >> 4 == 1:
            # The WMR inexplicably returns wind chill in degrees F, but everything
            # else in degrees C...
            windchill_F = (((packet[8] & 0x0f) << 8) + packet[7]) / 10.0
            _record['windchill'] = weewx.units.conversionDict['degree_F']['degree_C'](windchill_F)
        return _record
        
    def _barometer_packet(self, packet):
        SP  = float(((packet[3] & 0x0f) << 8) + packet[2])
        SLP = float(((packet[5] & 0x0f) << 8) + packet[4])
        SA = weewx.wxformulas.altimeter_pressure_Metric(SP, self.altitude)
        _record = {'barometer'   : SLP,
                   'pressure'    : SP,
                   'altimeter'   : SA,
                   'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        return _record
        
    def _uv_packet(self, packet):
        _record = {'UV'          : float(packet[5]),
                   'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        return _record
        
    
    def _wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in m/s"""
        _record = {'windSpeed'   : ((packet[6] << 4) + ((packet[5]) >> 4)) / 10.0,
                   'windDir'     : (packet[2] & 0x0f) * 360.0 / 16.0, 
                   'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        # Sometimes the station emits a wind gust that is less than the average wind.
        # Ignore it if this is the case.
        windGustSpeed = (((packet[5] & 0x0f) << 8) + packet[4]) / 10.0
        if windGustSpeed >= _record['windSpeed']:
            _record['windGust'] = windGustSpeed
        windSpeed=_record['windSpeed']
        print "Wind speed: ", windSpeed, "m/s; (", windSpeed*2.23694, " mph)"
        print "Wind gust : ", windGustSpeed, "m/s; (", windGustSpeed*2.23694, " mph)"
        return _record
    
    def _clock_packet(self, packet):
        """The clock packet is not used by weewx."""
        return None
    
    # Dictionary that maps a measurement code, to a function that can decode it:
    _dispatch_dict = {0x41: _rain_packet,
                      0x42: _temperature_packet,
                      0x46: _barometer_packet,
                      0x47: _uv_packet,
                      0x48: _wind_packet,
                      0x60: _clock_packet}
    
if __name__ == "__main__":
    station = WMR100(altitude=213.36)
    for pack in station.genLoopPackets():
        print pack
