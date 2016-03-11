#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes and functions for interfacing with an Oregon Scientific WMR100 station.
   The WMRS200 reportedly works with this driver (NOT the WMR200, which is a different beast).

    The following references were useful for figuring out the WMR protocol:
    
    From Per Ejeklint:
        https://github.com/ejeklint/WLoggerDaemon/blob/master/Station_protocol.md
        
    From Rainer Finkeldeh:
        http://www.bashewa.com/wmr200-protocol.php
        
    The WMR driver for the wfrog weather system:
        http://code.google.com/p/wfrog/source/browse/trunk/wfdriver/station/wmrs200.py
        
    Unfortunately, there is no documentation for PyUSB v0.4, so you have to back it out of the
    source code, available at:
        https://pyusb.svn.sourceforge.net/svnroot/pyusb/branches/0.4/pyusb.c
    
"""

import time
import operator
import syslog

import usb

import weewx.drivers
import weewx.wxformulas
import weeutil.weeutil

DRIVER_NAME = 'WMR100'
DRIVER_VERSION = "3.1"

def loader(config_dict, engine):  # @UnusedVariable
    return WMR100(**config_dict[DRIVER_NAME])    

def confeditor_loader():
    return WMR100ConfEditor()


class WMR100(weewx.drivers.AbstractDevice):
    """Driver for the WMR100 station."""
    
    def __init__(self, **stn_dict) :
        """Initialize an object of type WMR100.
        
        NAMED ARGUMENTS:
        
        model: Which station model is this?
        [Optional. Default is 'WMR100']

        stale_wind: Max time wind speed can be used to calculate wind chill
        before being declared unusable. [Optional. Default is 30 seconds]
        
        timeout: How long to wait, in seconds, before giving up on a response from the
        USB port. [Optional. Default is 15 seconds]
        
        wait_before_retry: How long to wait before retrying. [Optional.
        Default is 5 seconds]

        max_tries: How many times to try before giving up. [Optional.
        Default is 3]
        
        vendor_id: The USB vendor ID for the WMR [Optional. Default is 0xfde.
        
        product_id: The USB product ID for the WM [Optional. Default is 0xca01.
        
        interface: The USB interface [Optional. Default is 0]
        
        IN_endpoint: The IN USB endpoint used by the WMR. [Optional. Default is usb.ENDPOINT_IN + 1]
        """
        
        self.model             = stn_dict.get('model', 'WMR100')
        # TODO: Consider putting these in the driver loader instead:
        self.record_generation = stn_dict.get('record_generation', 'software')
        self.stale_wind        = float(stn_dict.get('stale_wind', 30.0))
        self.timeout           = float(stn_dict.get('timeout', 15.0))
        self.wait_before_retry = float(stn_dict.get('wait_before_retry', 5.0))
        self.max_tries         = int(stn_dict.get('max_tries', 3))
        self.vendor_id         = int(stn_dict.get('vendor_id',  '0x0fde'), 0)
        self.product_id        = int(stn_dict.get('product_id', '0xca01'), 0)
        self.interface         = int(stn_dict.get('interface', 0))
        self.IN_endpoint       = int(stn_dict.get('IN_endpoint', usb.ENDPOINT_IN + 1))

        self.last_totalRain = None
        self.openPort()

    def openPort(self):
        dev = self._findDevice()
        if not dev:
            syslog.syslog(syslog.LOG_ERR, "wmr100: Unable to find USB device (0x%04x, 0x%04x)" % (self.vendor_id, self.product_id))
            raise weewx.WeeWxIOError("Unable to find USB device")
        self.devh = dev.open()
        # Detach any old claimed interfaces
        try:
            self.devh.detachKernelDriver(self.interface)
        except usb.USBError:
            pass
        try:
            self.devh.claimInterface(self.interface)
        except usb.USBError, e:
            self.closePort()
            syslog.syslog(syslog.LOG_CRIT, "wmr100: Unable to claim USB interface. Reason: %s" % e)
            raise weewx.WeeWxIOError(e)
        
    def closePort(self):
        try:
            self.devh.releaseInterface()
        except usb.USBError:
            pass
        try:
            self.devh.detachKernelDriver(self.interface)
        except usb.USBError:
            pass
        
    def genLoopPackets(self):
        """Generator function that continuously returns loop packets"""
        
        # Get a stream of raw packets, then convert them, depending on the
        # observation type.
        
        for _packet in self.genPackets():
            try:
                _packet_type = _packet[1]
                if _packet_type in WMR100._dispatch_dict:
                    _record = WMR100._dispatch_dict[_packet_type](self, _packet)
                    if _record is not None:
                        yield _record
            except IndexError:
                syslog.syslog(syslog.LOG_ERR, "wmr100: Malformed packet. %s" % _packet)
                
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
                        syslog.syslog(syslog.LOG_DEBUG, "wmr100: Exception while calculating checksum.")
                        syslog.syslog(syslog.LOG_DEBUG, "****  %s" % e)
                else:
                    actual_checksum = (buff[-1] << 8) + buff[-2]
                    if computed_checksum == actual_checksum:
                        # Looks good. Yield the packet
                        yield buff
                    elif weewx.debug:
                        syslog.syslog(syslog.LOG_DEBUG, "wmr100: Bad checksum on buffer of length %d" % len(buff))
                # Throw away the next character (which will be 0xff):
                genBytes.next()
                # Start with a fresh buffer
                buff = []
            else:
                buff.append(ibyte)
             
    @property
    def hardware_name(self):
        return self.model
        
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
        
        try:
            # Only need to be sent after a reset or power failure of the station:
            self.devh.controlMsg(usb.TYPE_CLASS + usb.RECIP_INTERFACE,       # requestType
                                 0x0000009,                                  # request
                                 [0x20,0x00,0x08,0x01,0x00,0x00,0x00,0x00],  # buffer
                                 0x0000200,                                  # value
                                 0x0000000,                                  # index
                                 1000)                                       # timeout
        except usb.USBError, e:
            syslog.syslog(syslog.LOG_ERR, "wmr100: Unable to send USB control message")
            syslog.syslog(syslog.LOG_ERR, "****  %s" % e)
            # Convert to a Weewx error:
            raise weewx.WakeupError(e)
            
        nerrors=0
        while True:
            try:
                # Continually loop, retrieving "USB reports". They are 8 bytes long each.
                report = self.devh.interruptRead(self.IN_endpoint,
                                                 8, # bytes to read
                                                 int(self.timeout*1000))
                # While the report is 8 bytes long, only a smaller, variable portion of it
                # has measurement data. This amount is given by byte zero. Return each
                # byte, starting with byte one:
                for i in range(1, report[0]+1):
                    yield report[i]
                nerrors = 0
            except (IndexError, usb.USBError), e:
                syslog.syslog(syslog.LOG_DEBUG, "wmr100: Bad USB report received.")
                syslog.syslog(syslog.LOG_DEBUG, "***** %s" % e)
                nerrors += 1
                if nerrors>self.max_tries:
                    syslog.syslog(syslog.LOG_ERR, "wmr100: Max retries exceeded while fetching USB reports")
                    raise weewx.RetriesExceeded("Max retries exceeded while fetching USB reports")
                time.sleep(self.wait_before_retry)
    
    #===============================================================================
    #                         LOOP packet decoding functions
    #===============================================================================

    def _rain_packet(self, packet):
        
        # NB: in my experiments with the WMR100, it registers in increments of
        # 0.04 inches. Per Ejeklint's notes have you divide the packet values by
        # 10, but this would result in an 0.4 inch bucket --- too big. So, I'm
        # dividing by 100.
        _record = {'rainRate'          : ((packet[3] << 8) + packet[2]) / 100.0,
                   'hourRain'          : ((packet[5] << 8) + packet[4]) / 100.0,
                   'rain24'            : ((packet[7] << 8) + packet[6]) / 100.0,
                   'totalRain'         : ((packet[9] << 8) + packet[8]) / 100.0,
                   'rainBatteryStatus' : packet[0] >> 4,
                   'dateTime'          : int(time.time() + 0.5),
                   'usUnits'           : weewx.US}

        # Because the WMR does not offer anything like bucket tips, we must
        # calculate it by looking for the change in total rain. Of course, this
        # won't work for the very first rain packet.
        _record['rain'] = weewx.wxformulas.calculate_rain(_record['totalRain'], self.last_totalRain)
        self.last_totalRain = _record['totalRain']
        return _record

    def _temperature_packet(self, packet):
        _record = {'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        # Per Ejeklint's notes don't mention what to do if temperature is
        # negative. I think the following is correct. Also, from experience, we
        # know that the WMR has problems measuring dewpoint at temperatures
        # below about 20F. So, use software calculations instead.
        T = (((packet[4] & 0x7f) << 8) + packet[3])/10.0
        if packet[4] & 0x80 : T = -T
        R = float(packet[5])
        channel = packet[2] & 0x0f
        if channel == 0:
            _record['inTemp']      = T
            _record['inHumidity']  = R
            _record['inTempBatteryStatus'] = (packet[0] & 0x40) >> 6
        elif channel == 1:
            _record['outTemp']     = T
            _record['outHumidity'] = R
            # The WMR does not provide wind information in a temperature
            # packet, so we have to use old wind data to calculate wind chill,
            # provided it isn't too old and has gone stale. If no wind data has
            # been seen yet, then this will raise an AttributeError exception.
            try:
                if _record['dateTime'] - self.last_wind_record['dateTime'] <= self.stale_wind:
                    _record['windSpeed'] = self.last_wind_record['windSpeed']
            except AttributeError:
                pass
            _record['outTempBatteryStatus'] = (packet[0] & 0x40) >> 6
            # Save the record containing outside temperature to be used for calculating SLP barometer
            self.last_temperature_record = _record
        elif channel >= 2:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            _record['extraTemp%d'  % (channel-1)] = T
            _record['extraHumid%d' % (channel-1)] = R
            
        return _record
        
    def _temperatureonly_packet(self, packet):
        # function added by fstuyk to manage temperature-only sensor THWR800
        #
        _record = {'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        # Per Ejeklint's notes don't mention what to do if temperature is
        # negative. I think the following is correct. 
        T = (((packet[4] & 0x7f) << 8) + packet[3])/10.0
        if packet[4] & 0x80 : T = -T
        channel = packet[2] & 0x0f

        if channel == 0:
            _record['inTemp'] = T
            _record['inTempBatteryStatus'] = (packet[0] & 0x40) >> 6
        elif channel == 1:
            _record['outTemp'] = T
            # The WMR does not provide wind information in a temperature
            # packet, so we have to use old wind data to calculate wind chill,
            # provided it isn't too old and has gone stale. If no wind data has
            # been seen yet, then this will raise an AttributeError exception.
            try:
                if _record['dateTime'] - self.last_wind_record['dateTime'] <= self.stale_wind:
                    _record['windSpeed'] = self.last_wind_record['windSpeed']
            except AttributeError:
                pass
            _record['outTempBatteryStatus'] = (packet[0] & 0x40) >> 6
            # Save the record containing outside temperature to be used for calculating SLP barometer
            self.last_temperature_record = _record

        elif channel >= 2:
            # If additional temperature sensors exist (channel>=2), then
            # use observation types 'extraTemp1', 'extraTemp2', etc.
            _record['extraTemp%d' % (channel-1)] = T

        return _record

    def _barometer_packet(self, packet):
        SP = float(((packet[3] & 0x0f) << 8) + packet[2])
        # Although the WMR100 emits SLP, not all consoles in the series
        # (notably, the WMRS200) allow the user to set altitude. So, we must
        # calculate in software. 
        # SLP = float(((packet[5] & 0x0f) << 8) + packet[4])
        try:
            outTemp = self.last_temperature_record['outTemp']
        except (AttributeError, KeyError):
            outTemp = None
        _record = {'pressure'    : SP,
                   'outTemp'     : outTemp,
                   'dateTime'    : int(time.time() + 0.5),
                   'usUnits'     : weewx.METRIC}
        return _record
        
    def _uv_packet(self, packet):
        _record = {'UV'              : float(packet[3]),
                   'uvBatteryStatus' : packet[0] >> 4,
                   'dateTime'        : int(time.time() + 0.5),
                   'usUnits'         : weewx.METRIC}
        return _record

    def _wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""

        _record = {'windSpeed'         : ((packet[6] << 4) + ((packet[5]) >> 4)) / 10.0,
                   'windGust'          : (((packet[5] & 0x0f) << 8) + packet[4]) / 10.0,
                   'windDir'           : (packet[2] & 0x0f) * 360.0 / 16.0,
                   'windBatteryStatus' : (packet[0] >> 4),
                   'dateTime'          : int(time.time() + 0.5),
                   'usUnits'           : weewx.METRICWX}

        # Sometimes the station emits a wind gust that is less than the average wind.
        # If this happens, ignore it.
        if _record['windGust'] < _record['windSpeed']:
            _record['windGust'] = None
            _record['windGustDir'] = None
        else:
            # Otherwise, use the regular wind direction for the gust direction
            _record['windGustDir'] =_record['windDir']

        # Save the wind record to be used for windchill and heat index
        self.last_wind_record = _record
        return _record
    
    def _clock_packet(self, packet):
        """The clock packet is not used by weewx.
        
        However, the last time is saved in case getTime() is called."""
        tt = (2000+packet[8], packet[7], packet[6], packet[5], packet[4], 0, 0, 0, -1)
        self.last_time = time.mktime(tt)
        return None
    
    # Dictionary that maps a measurement code, to a function that can decode it:
    _dispatch_dict = {0x41: _rain_packet,
                      0x42: _temperature_packet,
                      0x46: _barometer_packet,
                      0x47: _uv_packet,
                      0x48: _wind_packet,
                      0x60: _clock_packet,
                      0x44: _temperatureonly_packet}


class WMR100ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR100]
    # This section is for the Oregon Scientific WMR100

    # The station model, e.g., WMR100, WMR100N, WMRS200
    model = WMR100

    # How long a wind record can be used to calculate wind chill (in seconds)
    stale_wind = 30

    # The driver to use:
    driver = weewx.drivers.wmr100
"""

    def modify_config(self, config_dict):
        print """
Setting rainRate calculation to hardware."""
        config_dict['StdWXCalculate']['rainRate'] = 'hardware'
