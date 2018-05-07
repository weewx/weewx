# Copyright (c) 2012 Will Page <compenguy@gmail.com>
# See the file LICENSE.txt for your full rights.
#
# Derivative of vantage.py and wmr100.py, credit to Tom Keffer

"""Classes and functions for interfacing with Oregon Scientific  WMR89,

See 
  https://www.wxforum.net/index.php?topic=27581
for documentation on the serial protocol

"""

import time
import operator
import syslog

import serial

import weewx.drivers

from math import exp

DRIVER_NAME = 'WMR89'
DRIVER_VERSION = "0.1.1"
DEFAULT_PORT = '/dev/ttyS0'

def loader(config_dict, engine):  # @UnusedVariable
    return WMR89(**config_dict[DRIVER_NAME])

def confeditor_loader():
    return WMR89ConfEditor()

def logmsg(level, msg):
    syslog.syslog(level, 'wmr89: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


class WMR89ProtocolError(weewx.WeeWxIOError):
    """Used to signal a protocol error condition"""


class SerialWrapper(object):
    """Wraps a serial connection returned from package serial"""

    def __init__(self, port):
        self.port = port
        # WMR89 specific settings
        self.serialconfig = {
            "baudrate": 128000,
            "bytesize": serial.EIGHTBITS,
            "parity": serial.PARITY_NONE,
            "stopbits": serial.STOPBITS_ONE,
            "timeout": 2,
            "xonxoff": False
        }

    def flush_input(self):
        self.serial_port.flushInput()

    def queued_bytes(self):
        return self.serial_port.inWaiting()

    def read(self, chars=1):
        _buffer = self.serial_port.read(chars)
        N = len(_buffer)
        if N != chars:
            raise weewx.WeeWxIOError("Expected to read %d chars; got %d instead" % (chars, N))
        return _buffer

    def readAll(self):
        _buffer = ''  
        while self.serial_port.inWaiting()>0:
          _buffer += self.serial_port.read()
        return _buffer

    def inWaiting(self):
        return self.serial_port.inWaiting() 
    
    def write(self, buf):
        self.serial_port.write(buf)

    def openPort(self):
        # Open up the port and store it
        self.serial_port = serial.Serial(self.port, **self.serialconfig)
        logdbg("Opened up serial port %s" % self.port)

    def closePort(self):
        self.serial_port.close()

#==============================================================================
#                           Class WMR89
#==============================================================================

class WMR89(weewx.drivers.AbstractDevice):
    """Driver for the Oregon Scientific WMR89 console.

    The connection to the console will be open after initialization"""

    DEFAULT_MAP = {
        'barometer': 'barometer',
        'pressure': 'pressure',
        'windSpeed': 'wind_speed',
        'windDir': 'wind_dir',
        'windGust': 'wind_gust',
        'windGustDir': 'wind_gust_dir',
        'windBatteryStatus': 'battery_status_wind',
        'inTemp': 'temperature_in',
        'outTemp': 'temperature_out',
        'extraTemp1': 'temperature_1',
        'extraTemp2': 'temperature_2',
        'extraTemp3': 'temperature_3',
        'extraTemp4': 'temperature_4',
        'extraTemp5': 'temperature_5',
        'extraTemp6': 'temperature_6',
        'extraTemp7': 'temperature_7',
        'extraTemp8': 'temperature_8',
        'inHumidity': 'humidity_in',
        'outHumidity': 'humidity_out',
        'extraHumid1': 'humidity_1',
        'extraHumid2': 'humidity_2',
        'extraHumid3': 'humidity_3',
        'extraHumid4': 'humidity_4',
        'extraHumid5': 'humidity_5',
        'extraHumid6': 'humidity_6',
        'extraHumid7': 'humidity_7',
        'extraHumid8': 'humidity_8',
        'inTempBatteryStatus': 'battery_status_in',
        'outTempBatteryStatus': 'battery_status_out',
        'extraBatteryStatus1': 'battery_status_1', # was batteryStatusTHx
        'extraBatteryStatus2': 'battery_status_2', # or batteryStatusTx
        'extraBatteryStatus3': 'battery_status_3',
        'extraBatteryStatus4': 'battery_status_4',
        'extraBatteryStatus5': 'battery_status_5',
        'extraBatteryStatus6': 'battery_status_6',
        'extraBatteryStatus7': 'battery_status_7',
        'extraBatteryStatus8': 'battery_status_8',
        'inDewpoint': 'dewpoint_in',
        'dewpoint': 'dewpoint_out',
        'dewpoint0': 'dewpoint_0',
        'dewpoint1': 'dewpoint_1',
        'dewpoint2': 'dewpoint_2',
        'dewpoint3': 'dewpoint_3',
        'dewpoint4': 'dewpoint_4',
        'dewpoint5': 'dewpoint_5',
        'dewpoint6': 'dewpoint_6',
        'dewpoint7': 'dewpoint_7',
        'dewpoint8': 'dewpoint_8',
        'rain': 'rain',
        'rainTotal': 'rain_total',
        'rainRate': 'rain_rate',
        'hourRain': 'rain_hour',
        'rain24': 'rain_24',
        'yesterdayRain': 'rain_yesterday',
        'rainBatteryStatus': 'battery_status_rain',
        'windchill': 'windchill'}

    def __init__(self, **stn_dict):
        """Initialize an object of type WMR89.

        NAMED ARGUMENTS:

        model: Which station model is this?
        [Optional. Default is 'WMR89']

        port: The serial port of the WM89.
        [Required if serial communication]

        baudrate: Baudrate of the port.
        [Optional. Default 9600]

        timeout: How long to wait before giving up on a response from the
        serial port.
        [Optional. Default is 5]
        """

        loginf('driver version is %s' % DRIVER_VERSION)
        self.model = stn_dict.get('model', 'WMR89')
        self.sensor_map = dict(self.DEFAULT_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        loginf('sensor map is %s' % self.sensor_map)
        self.last_rain_total = None

        # Create the specified port
        self.port = WMR89._port_factory(stn_dict)

        # Open it up:
        self.port.openPort()

    @property
    def hardware_name(self):
        return self.model

    def openPort(self):
        """Open up the connection to the console"""
        self.port.openPort()

    def closePort(self):
        """Close the connection to the console. """
        self.port.closePort()

    def genLoopPackets(self):
        """Generator function that continuously returns loop packets"""
        buf = []
        while True:
            # request data 
            if self.port.inWaiting()==0:
                self.port.write('d100'.decode("hex"))
                time.sleep(0.5)

            # read data
            buf = self.port.readAll()

            if len(buf) > 0 :
               decode = buf.split('f2f2'.decode('hex'))
               decode = filter(None,decode)
               #loop all packages 
               for i in range(len(decode)):
                 logdbg("Received WMR89 data packet: %s" % decode[i].encode('hex'))
                 _record = None
                 if weewx.debug >= 2:
                    self.log_packet(decode[i])

                 if decode[i][0].encode('hex')=='b0': #date/time NOK
                    _record = self._wmr89_time_packet(decode[i])
                 elif decode[i][0].encode('hex')=='b1': #Rain NOK
                    _record = self._wmr89_rain_packet(decode[i])
                 elif decode[i][0].encode('hex')=='b2': #Wind OK 
                    _record = self._wmr89_wind_packet(decode[i])
                 elif decode[i][0].encode('hex')=='b4': #Pressure OK
                    _record = self._wmr89_pressure_packet(decode[i])
                 elif decode[i][0].encode('hex')=='b5':#T/Hum  OK
                    _record = self._wmr89_temp_packet(decode[i])
                 else:
                    logdbg("Invalid data packet (%s)." % decode[i].encode('hex'))

                 if _record is not None:
                   _record = self._sensors_to_fields(_record, self.sensor_map)
                 
                 if _record is not None:
                        #print _record
                        yield _record
 
 

    @staticmethod
    def _sensors_to_fields(oldrec, sensor_map):
        # map a record with observation names to a record with db field names
        if oldrec:
            newrec = dict()
            for k in sensor_map:
                if sensor_map[k] in oldrec:
                    newrec[k] = oldrec[sensor_map[k]]
            if newrec:
                newrec['dateTime'] = oldrec['dateTime']
                newrec['usUnits'] = oldrec['usUnits']
                return newrec
        return None

    #==========================================================================
    #              Oregon Scientific WMR89 utility functions
    #==========================================================================

    @staticmethod
    def _port_factory(stn_dict):
        """Produce a serial port object"""

        # Get the connection type. If it is not specified, assume 'serial':
        connection_type = stn_dict.get('type', 'serial').lower()

        if connection_type == "serial":
            port = stn_dict['port']
            return SerialWrapper(port)
        raise weewx.UnsupportedFeature(stn_dict['type'])

    def log_packet(self, packet):
        #packet_str = ','.join(["x%x" % v for v in packet])
        print "%d, %s, %s" % (int(time.time() + 0.5), time.asctime(), packet.encode('hex'))

    def _wmr89_wind_packet(self, packet):
        """Decode a wind packet. Wind speed will be in kph"""
        ## 0  1  2  3  4  5  6  7  8  9  10 
        ## b2 0b 00 00 00 00 00 02 7f 01 3e
        ##    ?     Wa    Wg    Wd Wc ?  CS?
        Wa=(ord(packet[3])*0.36)
        Wg=(ord(packet[5])*0.36)
        Wd=(ord(packet[7])*22.5)
        Wc=ord(packet[8])  
        if Wc<125:
          Wc=((ord(packet[8])-32)*5/9)
        elif Wc==125:
          Wc=None
        elif Wc>125:
          Wc=(((Wc-255)-32)*5/9)        

        _record = {
            'wind_speed': float(Wa),
            'wind_dir': float(Wd),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC,
            'wind_gust': float(Wg),
            'windchill': Wc
        }
        
        return _record

    def _wmr89_rain_packet(self, packet):
        ## 0  1  2  3  4  5  6  7    8  9  10 11 12 13 14 15 16
        ## b1 11 ff fe 00 08 00 22   00 48 0e 01 01 0d 18 03 66
        ## b1 11 ff fe 00 11 00 11   00 95 0e 01 01 0d 18 03 ab: 4,3 mm  / 11 = 17
        ## b1 11 ff fe 00 ca 00 db   00 5f 0e 01 01 0d 18 04 f8: 116,3 mm - 163,1 / db=219 / 
        ## b1 11 ff fe 00 2a 00 3b   00 be 0e 01 01 0d 18 04 17: 270,8mm - 309,6 / 3b=59 / 
        ##    ?  r/h-- rain  last24  Rtot  ?  ?  ?  ?  ?  ?  CS?
        # station units are inch and inch/hr while the internal metric units are
        # cm and cm/hr. 

        # byte 2-3: rain per hour  
        # fffe = no value
        if packet[2:4].encode('hex')=='fffe':
           Rh = None
        else:
           Rh = (256*ord(packet[2])+ord(packet[3]))*2.54/100 

        # byte 4-5: actual rain /100 in inch
        Ra = (256*ord(packet[4])+ord(packet[5]))*2.54/100
        # byte 6-7: last 24h  /100 in inch
        R24 = (256*ord(packet[6])+ord(packet[7]))*2.54/100
        # byte 8-9: tot /100 in inch
        Rtot = (256*ord(packet[8])+ord(packet[9]))*2.54/100



        _record = {
            'rain_rate': Ra,
            'rain_total': Rtot,
            'rain_hour': Rh,
            'rain_24': R24,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }
	
	_record['rain'] = weewx.wxformulas.calculate_rain(_record['rain_total'], self.last_rain_total)            
        self.last_rain_total = _record['rain_total']
	
        return _record


    def _wmr89_temp_packet(self, packet):
        ## b50b01006c005408fd0286
        ## b50b027fff33ff7fff04f0
        ## b50b037fff33ff7fff04f1
        ## b50b0100da002f0afd02d1

        ## 0  1  2      3  4  5  6   7   8  9  10
        ## b5 0b 01     00 12 00 54  ff  fd 03 23
        ## b5 0b 01     00 d7 00 2e  0a  fd 02 cd <<-- batterie low
        ## b5 0b 01     00 d6 00 2e  09  fd 02 cb
        ##    ?  sensor temp  ?  hum dew ?  ?  ?
        temp=256*ord(packet[3])+ord(packet[4])
        if temp>=32768:
           temp=temp-65536
        temp=(temp*0.1)

        # According to specifications the WMR89 humidity range are 25/95% 
        if ord(packet[6])==254:
            hum=95
        elif ord(packet[6])==252:
            hum=25
        else:
            hum=float(ord(packet[6]))

        dew=(ord(packet[7]))
        if dew==125:
          dew=None
        elif dew>125:
          dew=((dew-256))  

        if ord(packet[8])==253:
	  heatindex=None
        else:
          heatindex=float(ord(packet[7]))

        if (packet[2].encode('hex')=='00'):
          _record = {
            'humidity_in': hum,
            'temperature_in': float(temp),
            'dewpoint_in': dew,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
          }
        elif (packet[2].encode('hex')=='01'):
          _record = {
            'humidity_out': hum,
            'temperature_out': float(temp),
            'dewpoint_out': dew,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
          }
        elif (packet[2].encode('hex')=='02'):
          _record = {
            'humidity_1': hum,
            'temperature_1': float(temp),
            'dewpoint_1': dew,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
          }
        elif (packet[2].encode('hex')=='03'):
          _record = {
            'humidity_2': hum,
            'temperature_2': float(temp),
            'dewpoint_2': dew,
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
          }
        else:
          _record=None

        return _record



    def _wmr89_pressure_packet(self, packet):
        ## 0  1  2  3  4  5  6  7  8
        ## b4 09 27 e9 27 e9 03 02 e0
        ## b4 09 27 ea 28 16 03 02 0f
        ##    ?  baro  press ?  ?  ?
        ## weather display? barometric compensation
        Pr=str((256*ord(packet[2])+ord(packet[3]))*0.1)
        bar=str((256*ord(packet[4])+ord(packet[5]))*0.1)
   
        _record = {
            'pressure': float(Pr),
            'barometer': float(bar),
            'dateTime': int(time.time() + 0.5),
            'usUnits': weewx.METRIC
        }

        return _record





    def _wmr89_time_packet(self, packet):
        """The (partial) time packet is not used by weewx.
        However, the last time is saved in case getTime() is called."""
        #DateTime='20'+str(ord(packet[5])).zfill(2)+'/'+str(ord(packet[6])).zfill(2)+'/'+str(ord(packet[7])).zfill(2)+' '+str(ord(packet[8])).zfill(2)+':'+str(ord(packet[9])).zfill(2

        #min1, min10 = self._get_nibble_data(packet[1:])
        #minutes = min1 + ((min10 & 0x07) * 10)

        #cur = time.gmtime()
        #self.last_time = time.mktime(
        #    (cur.tm_year, cur.tm_mon, cur.tm_mday,
        #     cur.tm_hour, minutes, 0,
        #     cur.tm_wday, cur.tm_yday, cur.tm_isdst))
        return None



class WMR89ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[WMR89]
    # This section is for the Oregon Scientific WMR89

    # Connection type. For now, 'serial' is the only option. 
    type = serial

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The station model, e.g., WMR89
    model = WMR89

    # The driver to use:
    driver = weewx.drivers.wmr89
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}

    def modify_config(self, config_dict):
        print """
Setting rainRate, windchill, and dewpoint calculations to hardware."""
        config_dict.setdefault('StdWXCalculate', {})
        config_dict['StdWXCalculate'].setdefault('Calculations', {})
        config_dict['StdWXCalculate']['Calculations']['rainRate'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['windchill'] = 'hardware'
        config_dict['StdWXCalculate']['Calculations']['dewpoint'] = 'hardware'

# Define a main entry point for basic testing without the weewx engine.
# Invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/wmr89.py

if __name__ == '__main__':
    import optparse

    usage = """Usage: %prog --help
       %prog --version
       %prog --gen-packets [--port=PORT]"""

    syslog.openlog('wmr89', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    weewx.debug = 2
    
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='Display driver version')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='The port to use. Default is %s' % DEFAULT_PORT,
                      default=DEFAULT_PORT)
    parser.add_option('--gen-packets', dest='gen_packets', action='store_true',
                      help="Generate packets indefinitely")
    
    (options, args) = parser.parse_args()

    if options.version:
        print "WMR89 driver version %s" % DRIVER_VERSION
        exit(0)

    if options.gen_packets:
        syslog.syslog(syslog.LOG_DEBUG, "wmr89: Running genLoopPackets()")
        stn_dict = {'port': options.port}
        stn = WMR89(**stn_dict)
        
        for packet in stn.genLoopPackets():
            print packet
