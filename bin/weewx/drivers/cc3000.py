#!/usr/bin/env python
#
# Copyright 2014 Matthew Wall
# See the file LICENSE.txt for your full rights.

"""Driver for CC3000 data logger

http://www.rainwise.com/products/attachments/6832/20110518125531.pdf

There are at least two variants: CC3000 and CC3000R.  The CC3000 communicates
using FTDI USB serial bridge.  The CC3000R has both RS-232 and RS-485 serial
ports, only one of which may be used at a time.

The CC3000 includes a temperature sensor - that is the source of inTemp.

The CC3000 users 4 AA batteries to maintain its clock.

This driver does not support hardware record_generation.  It does support
catchup on startup.
"""

# FIXME: do a partial read of memory based on interval size
# FIXME: support non-fixed interval size

from __future__ import with_statement
import datetime
import serial
import string
import syslog
import time

import weewx.drivers

DRIVER_NAME = 'CC3000'
DRIVER_VERSION = '0.9'

def loader(config_dict, engine):
    return CC3000Driver(**config_dict[DRIVER_NAME])

def configurator_loader(config_dict):
    return CC3000Configurator()

def confeditor_loader():
    return CC3000ConfEditor()


DEFAULT_PORT = '/dev/ttyS0'
DEBUG_READ = 0
DEBUG_CHECKSUM = 0
DEBUG_OPENCLOSE = 0

def logmsg(level, msg):
    syslog.syslog(level, 'cc3000: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class ChecksumMismatch(weewx.WeeWxIOError):
    def __init__(self, a, b, buf=None):
        msg = "Checksum mismatch: 0x%04x != 0x%04x" % (a,b)
        if buf is not None:
            msg = "%s (%s)" % (msg, _fmt(buf))
        weewx.WeeWxIOError.__init__(self, msg)


class CC3000Configurator(weewx.drivers.AbstractConfigurator):
    def add_options(self, parser):
        super(CC3000Configurator, self).add_options(parser)
        parser.add_option("--info", dest="info", action="store_true",
                          help="display weather station configuration")
        parser.add_option("--current", dest="current", action="store_true",
                          help="display current weather readings")
        parser.add_option("--history", dest="nrecords", type=int, metavar="N",
                          help="display N records (0 for all records)")
        parser.add_option("--history-since", dest="nminutes",
                          type=int, metavar="N",
                          help="display records since N minutes ago")
        parser.add_option("--clear-memory", dest="clear", action="store_true",
                          help="clear station memory")
        parser.add_option("--set-clock", dest="clock", action="store_true",
                          help="set station clock to computer time")
        parser.add_option("--set-interval", dest="interval",
                          type=int, metavar="N",
                          help="set logging interval to N minutes")
        parser.add_option("--set-units", dest="units", metavar="UNITS",
                          help="set units to METRIC or ENGLISH")

    def do_options(self, options, parser, config_dict, prompt):
        self.station = CC3000Driver(**config_dict[DRIVER_NAME])
        if options.nrecords is not None:
            self.show_history(options.nrecords)
        elif options.current:
            self.show_current()
        elif options.clock:
            self.set_clock(prompt)
        elif options.interval is not None:
            self.set_interval(options.interval, prompt)
        elif options.units is not None:
            self.set_units(options.units, prompt)
        elif options.clear:
            self.clear_memory(prompt)
        else:
            self.show_info()
        self.station.closePort()

    def show_info(self):
        """Query the station then display the settings."""
        print "firmware:", self.station.get_version()
        print "time:", self.station.get_time()
        print "units:", self.station.get_units()
        print "memory:", self.station.get_status()
        print "interval:", self.station.get_interval()

    def show_history(self, nrecords=0):
        for r in self.station.get_records(nrecords):
            print r

    def show_current(self):
        print self.station.get_current()

    def clear_memory(self, prompt):
        ans = None
        while ans not in ['y', 'n']:
            print self.station.get_status()
            if prompt:
                ans = raw_input("Clear console memory (y/n)? ")
            else:
                print 'Clearing console memory'
                ans = 'y'
            if ans == 'y':
                self.station.clear_memory()
                print self.station.get_status()
            elif ans == 'n':
                print "Clear memory cancelled."

    def set_interval(self, interval, prompt):
        ans = None
        while ans not in ['y', 'n']:
            print "Interval is", self.station.get_interval()
            if prompt:
                ans = raw_input("Set interval to %d minutes (y/n)? " % interval)
            else:
                print "Setting interval to %d minutes" % interval
                ans = 'y'
            if ans == 'y':
                self.station.set_interval(interval)
                print "Interval is now", self.station.get_interval()
            elif ans == 'n':
                print "Set interval cancelled."

    def set_clock(self, prompt):
        ans = None
        while ans not in ['y', 'n']:
            print "Station clock is", self.station.get_time()
            now = datetime.datetime.now()
            if prompt:
                ans = raw_input("Set station clock to %s (y/n)? " % now)
            else:
                print "Setting station clock to %s" % now
                ans = 'y'
            if ans == 'y':
                self.station.set_time()
                print "Station clock is now", self.station.get_time()
            elif ans == 'n':
                print "Set clock cancelled."

    def set_units(self, units, prompt):
        ans = None
        while ans not in ['y', 'n']:
            print "Station units is", self.station.get_units()
            if prompt:
                ans = raw_input("Set station units to %s (y/n)? " % units)
            else:
                print "Setting station units to %s" % units
                ans = 'y'
            if ans == 'y':
                self.station.set_units(units)
                print "Station units is now", self.station.get_units()
            elif ans == 'n':
                print "Set units cancelled."


class CC3000Driver(weewx.drivers.AbstractDevice):
    """weewx driver that communicates with a RainWise CC3000 data logger."""

    # map rainwise names to weewx names
    DEFAULT_LABEL_MAP = { 'TIMESTAMP': 'TIMESTAMP',
                          'TEMP OUT': 'outTemp',
                          'HUMIDITY': 'outHumidity',
                          'WIND DIRECTION': 'windDir',
                          'WIND SPEED': 'windSpeed',
                          'WIND GUST': 'windGust',
                          'PRESSURE': 'pressure',
                          'TEMP IN': 'inTemp',
                          'RAIN': 'day_rain_total',
                          'STATION BATTERY': 'consBatteryVoltage',
                          'BATTERY BACKUP': 'bkupBatteryVoltage',
                          'SOLAR RADIATION': 'radiation',
                          'UV INDEX': 'UV',
                          }

    def __init__(self, **stn_dict):
        self.port = stn_dict.get('port', DEFAULT_PORT)
        self.polling_interval = float(stn_dict.get('polling_interval', 1))
        self.model = stn_dict.get('model', 'CC3000')
        self.use_station_time = stn_dict.get('use_station_time', True)
        self.max_tries = int(stn_dict.get('max_tries', 5))
        self.retry_wait = int(stn_dict.get('retry_wait', 60))
        self.label_map = stn_dict.get('label_map', self.DEFAULT_LABEL_MAP)

        self._archive_interval = None
        self.header = None
        self.units = None
        self.last_rain = None

        loginf('driver version is %s' % DRIVER_VERSION)
        loginf('using serial port %s' % self.port)
        loginf('polling interval is %s seconds' % self.polling_interval)
        loginf('using %s time' %
               ('station' if self.use_station_time else 'computer'))

        self._init_station_with_retries()

        loginf('archive_interval is %s' % self._archive_interval)
        loginf('header is %s' % self.header)
        loginf('units are %s' % self.units)

        global DEBUG_READ
        DEBUG_READ = int(stn_dict.get('debug_read', 0))
        global DEBUG_CHECKSUM
        DEBUG_CHECKSUM = int(stn_dict.get('debug_checksum', 0))
        global DEBUG_OPENCLOSE
        DEBUG_OPENCLOSE = int(stn_dict.get('debug_openclose', 0))

    def genLoopPackets(self):
        units = weewx.US if self.units == 'ENGLISH' else weewx.METRIC
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                with CC3000(self.port) as station:
                    values = station.get_current_data()
                ntries = 0
                data = self._parse_current(values)
                ts = data.get('TIMESTAMP')
                if ts is not None:
                    if not self.use_station_time:
                        ts = int(time.time() + 0.5)
                    packet = {'dateTime': ts, 'usUnits': units}
                    packet.update(data)
                    self._augment_packet(packet)
                    yield packet
                if self.polling_interval:
                    time.sleep(self.polling_interval)
            except (serial.serialutil.SerialException, weewx.WeeWxIOError), e:
                logerr("Failed attempt %d of %d to get data: %s" %
                       (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded" % self.max_tries
            logerr(msg)
            raise weewx.RetriesExceeded(msg)

    def genStartupRecords(self, since_ts):
        """Return archive records from the data logger.  Download all records
        then return the subset since the indicated timestamp.

        This assumes that the units are consistent for the entire history.

        NB: using gen_records did not work very well - bytes were corrupted.
        so we use more memory and load everything into memory first.
        """
        logdbg("genStartupRecords: since_ts=%s" % since_ts)
        nrec = 0
        # figure out how many records we need to download
        if since_ts is not None:
            delta = int(time.time()) - since_ts
            nrec = int(delta / self._archive_interval)
            logdbg("genStartupRecords: nrec=%s delta=%s" % (nrec, delta))
            if nrec == 0:
                return
        logdbg("genStartupRecords: nrec=%s" % nrec)
        units = weewx.US if self.units == 'ENGLISH' else weewx.METRIC
        with CC3000(self.port) as station:
            records = station.get_records(nrec)
            cnt = len(records)
            loginf("found %d records" % cnt)
            i = 0
            for r in records:
                i += 1
                if i % 100 == 0:
                    logdbg("record %d of %d" % (i, cnt))
                if r[0] != 'REC':
                    logdbg("non REC item: %s" % r[0])
                    continue
                data = self._parse_historical(r[1:])
                if data['TIMESTAMP'] > since_ts:
                    packet = {'dateTime': data['TIMESTAMP'],
                              'usUnits': units,
                              'interval': self._archive_interval}
                    packet.update(data)
                    self._augment_packet(packet)
                    yield packet

    @property
    def hardware_name(self):
        return self.model

    @property
    def archive_interval(self):
        return self._archive_interval

    def getTime(self):
        with CC3000(self.port) as station:
            v = station.get_time()
        return _to_ts(v)

    def setTime(self):
        with CC3000(self.port) as station:
            station.set_time()

    def get_current(self):
        with CC3000(self.port) as station:
            data = station.get_current_data()
        return self._parse_current(data)

    def get_records(self, nrec):
        with CC3000(self.port) as station:
            records = station.get_records(nrec)
        return records

    def get_time(self):
        with CC3000(self.port) as station:
            return station.get_time()

    def set_time(self):
        with CC3000(self.port) as station:
            station.set_time()

    def get_units(self):
        with CC3000(self.port) as station:
            return station.get_units()

    def set_units(self, units):
        with CC3000(self.port) as station:
            station.set_units(units)

    def get_interval(self):
        with CC3000(self.port) as station:
            return station.get_interval()

    def set_interval(self, interval):
        with CC3000(self.port) as station:
            station.set_interval(interval)

    def clear_memory(self):
        with CC3000(self.port) as station:
            station.clear_memory()

    def get_version(self):
        with CC3000(self.port) as station:
            return station.get_version()

    def get_status(self):
        with CC3000(self.port) as station:
            return station.get_memory_status()

    def _init_station_with_retries(self):
        for cnt in xrange(self.max_tries):
            try:
                self._init_station()
                return
            except (serial.serialutil.SerialException, weewx.WeeWxIOError), e:
                logerr("Failed attempt %d of %d to initialize station: %s" %
                       (cnt + 1, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            raise weewx.RetriesExceeded("Max retries (%d) exceeded while initializing station" % self.max_tries)

    def _init_station(self):
        with CC3000(self.port) as station:
            station.flush()
            station.set_echo()
            logdbg('get archive interval')
            self._archive_interval = 60 * station.get_interval()
            logdbg('get header')
            self.header = self._parse_header(station.get_header())
            logdbg('get units')
            self.units = station.get_units()

    def _augment_packet(self, packet):

        # calculate the rain
        if self.last_rain is not None:
            if packet['day_rain_total'] > self.last_rain:
                packet['rain'] = packet['day_rain_total'] - self.last_rain
            else:
                packet['rain'] = None # counter reset
        else:
            packet['rain'] = None
        self.last_rain = packet['day_rain_total']

    def _parse_current(self, values):
        return self._parse_values(values, "%Y/%m/%d %H:%M:%S")

    def _parse_historical(self, values):
        return self._parse_values(values, "%Y/%m/%d %H:%M")

    def _parse_values(self, values, fmt):
        data = {}
        for i, v in enumerate(values):
            if i >= len(self.header):
                continue
            label = self.label_map.get(self.header[i])
            if label is None:
                continue
            if label == 'TIMESTAMP':
                data[label] = _to_ts(v, fmt)
            else:
                data[label] = float(v)
        return data

    def _parse_header(self, header):
        h = []
        for v in header:
            if v == 'HDR' or v[0:1] == '!':
                continue
            v = v.replace('"', '')
            h.append(v)
        return h

def _to_ts(tstr, fmt="%Y/%m/%d %H:%M:%S"):
    return time.mktime(time.strptime(tstr, fmt))

def _format_bytes(buf):
    return ' '.join(["%0.2X" % ord(c) for c in buf])

def _fmt(buf):
    return filter(lambda x: x in string.printable, buf)

# calculate the crc for a string using CRC-16-CCITT
# http://bytes.com/topic/python/insights/887357-python-check-crc-frame-crc-16-ccitt
def _crc16(data):
    reg = 0x0000
    data += '\x00\x00'
    for byte in data:
        mask = 0x80
        while mask > 0:
            reg <<= 1
            if ord(byte) & mask:
                reg += 1
            mask >>= 1
            if reg > 0xffff:
                reg &= 0xffff
                reg ^= 0x1021
    return reg

def _check_crc(buf):
    idx = buf.find('!')
    if idx < 0:
        return
    cs = buf[idx+1:idx+5]
    if DEBUG_CHECKSUM:
        logdbg("found checksum at %d: %s" % (idx, cs))
    a = _crc16(buf[0:idx]) # calculate checksum
    if DEBUG_CHECKSUM:
        logdbg("calculated checksum %x" % a)
    b = int(cs, 16) # checksum provided in data
    if a != b:
        raise ChecksumMismatch(a, b, buf)

class CC3000(object):
    def __init__(self, port):
        self.port = port
        self.baudrate = 115200
        self.timeout = 5
        self.serial_port = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _, value, traceback):
        self.close()

    def open(self):
        if DEBUG_OPENCLOSE:
            logdbg("open serial port %s" % self.port)
        self.serial_port = serial.Serial(self.port, self.baudrate,
                                         timeout=self.timeout)

    def close(self):
        if self.serial_port is not None:
            if DEBUG_OPENCLOSE:
                logdbg("close serial port %s" % self.port)
            self.serial_port.close()
            self.serial_port = None

    def read(self, nchar=1):
        buf = self.serial_port.read(nchar)
        n = len(buf)
        if n != nchar:
            if n:
                logdbg("partial buffer: '%s'" %
                       ' '.join(["%0.2X" % ord(c) for c in buf]))
            raise weewx.WeeWxIOError("Read expected %d chars, got %d" %
                                     (nchar, n))
        return buf

    def write(self, data):
        n = self.serial_port.write(data)
        if n is not None and n != len(data):
            raise weewx.WeeWxIOError("Write expected %d chars, sent %d" %
                                     (len(data), n))

    def flush(self):
        self.flush_input()
        self.flush_output()

    def flush_input(self):
        logdbg("flush input buffer")
        self.serial_port.flushInput()

    def flush_output(self):
        logdbg("flush output buffer")
        self.serial_port.flushOutput()

    def queued_bytes(self):
        return self.serial_port.inWaiting()

    def command(self, cmd):
        self.write("%s\r" % cmd)
        data = self.get_data()
        data = data.strip()
        if data != cmd:
            raise weewx.WeeWxIOError("Command failed: cmd='%s' reply='%s' (%s)"
                                     % (cmd, _fmt(data), _format_bytes(data)))
        return self.get_data()

    def send_cmd(self, cmd):
        """Any command must be terminated with a CR"""
        self.write("%s\r" % cmd)

    def get_data(self):
        """The station sends CR NL before and after any response.  Some
        responses have a 4-byte CRC checksum at the end, indicated with an
        exclamation.  Not every response has a checksum.
        """
        buf = []
        while True:
            c = self.read()
            if c == '\r':
                if buf == 'OK' or buf == 'ERROR':
                    break
                c = self.read()
                if c == '\n':
                    break
                else:
                    raise weewx.WeeWxIOError("Unexpected byte 0x%0.2X" % ord(c))
            if c in string.printable:
                buf.append(c)
            else:
                loginf("skipping unprintable character 0x%0.2X" % ord(c))
        data = ''.join(buf)
        if DEBUG_READ:
            logdbg("got bytes: '%s' (%s)" % (_fmt(data), _format_bytes(data)))
        _check_crc(data)
        return data

    def set_echo(self, cmd='ON'):
        logdbg("set echo to %s" % cmd)
        data = self.command('ECHO=%s' % cmd)
        if data != 'OK':
            raise weewx.WeeWxIOError("Set ECHO failed: %s" % _fmt(data))

    def get_header(self):
        data = self.command("HEADER")
        cols = data.split(',')
        if cols[0] != 'HDR':
            raise weewx.WeeWxIOError("Expected HDR, got %s" % cols[0])
        return cols

    def get_current_data(self):
        data = self.command("NOW")
        if data == 'NO DATA' or data == 'NO DATA RECEIVED':
            loginf("No data from sensors")
            return []
        values = data.split(',')
        return values

    def get_memory_status(self):
        data = self.command("MEM=?")
        logdbg("memory status: %s" % _fmt(data))
        return data

    def clear_memory(self):
        logdbg("clear memory")
        data = self.command("MEM=CLEAR")
        if data != 'OK':
            raise weewx.WeeWxIOError("Failed to clear memory: %s" % _fmt(data))

    def gen_records(self, nrec):
        """generator function for getting records from the device"""
        cmd = "DOWNLOAD"
        if nrec:
            cmd += "=%d" % nrec
        self.send_cmd(cmd)
        n = 0
        while True:
            try:
                data = self.get_data()
                if data == 'OK':
                    logdbg("end of records")
                    break
                values = data.split(',')
                if values[0] == 'REC':
                    logdbg("record %d" % n)
                    n += 1
                    yield values
                else:
                    logdbg("skipping '%s'" % values[0])
            except ChecksumMismatch, e:
                logerr("record failed: %s" % e)

    def get_records(self, nrec=0):
        records = []
        for r in self.gen_records(nrec):
            records.append(r)
        return records

    def get_time(self):
        data = self.command("TIME=?")
        return data

    def set_time(self):
        ts = time.time()
        tstr = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(ts))
        logdbg("set time to %s (%s)" % (tstr, ts))
        s = "TIME=%s" % tstr
        data = self.command(s)
        if data != 'OK':
            raise weewx.WeeWxIOError("Failed to set time to %s: %s" %
                                     (s, _fmt(data)))

    def get_units(self):
        data = self.command("UNITS=?")
        return data

    def set_units(self, units='METRIC'):
        logdbg("set units to %s" % units)
        data = self.command("UNITS=%s" % units)
        if data != 'OK':
            raise weewx.WeeWxIOError("Failed to set units to %s: %s" %
                                     (units, _fmt(data)))

    def get_interval(self):
        data = self.command("LOGINT=?")
        return int(data)

    def set_interval(self, interval=5):
        logdbg("set logging interval to %d minutes" % interval)
        data = self.command("LOGINT=%d" % interval)
        if data != 'OK':
            raise weewx.WeeWxIOError("Failed to set logging interval: %s" %
                                     _fmt(data))

    def get_version(self):
        data = self.command("VERSION")
        return data


class CC3000ConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[CC3000]
    # This section is for RainWise MarkIII weather stations and CC3000 logger.

    # Serial port such as /dev/ttyS0, /dev/ttyUSB0, or /dev/cuaU0
    port = /dev/ttyUSB0

    # The station model, e.g., CC3000 or CC3000R
    model = CC3000

    # The driver to use:
    driver = weewx.drivers.cc3000
"""

    def prompt_for_settings(self):
        print "Specify the serial port on which the station is connected, for"
        print "example /dev/ttyUSB0 or /dev/ttyS0."
        port = self._prompt('port', '/dev/ttyUSB0')
        return {'port': port}


# define a main entry point for basic testing without weewx engine and service
# overhead.  invoke this as follows from the weewx root dir:
#
# PYTHONPATH=bin python bin/weewx/drivers/cc3000.py

if __name__ == '__main__':
    import optparse

    usage = """%prog [options] [--help]"""

    syslog.openlog('cc3000', syslog.LOG_PID | syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='display driver version')
    parser.add_option('--test-crc', dest='testcrc', action='store_true',
                      help='test crc')
    parser.add_option('--port', dest='port', metavar='PORT',
                      help='port to which the station is connected',
                      default=DEFAULT_PORT)
    parser.add_option('--get-version', dest='getver', action='store_true',
                      help='display firmware version')
    parser.add_option('--get-status', dest='status', action='store_true',
                      help='display memory status')
    parser.add_option('--get-current', dest='getcur', action='store_true',
                      help='display current data')
    parser.add_option('--get-records', dest='getrec', action='store_true',
                      help='display records from station memory')
    parser.add_option('--get-header', dest='gethead', action='store_true',
                      help='display data header')
    parser.add_option('--get-units', dest='getunits', action='store_true',
                      help='display units')
    parser.add_option('--set-units', dest='setunits', metavar='UNITS',
                      help='set units to ENGLISH or METRIC')
    parser.add_option('--get-time', dest='gettime', action='store_true',
                      help='display station time')
    parser.add_option('--set-time', dest='settime', action='store_true',
                      help='set station time to computer time')
    parser.add_option('--get-interval', dest='getint', action='store_true',
                      help='display logging interval, in seconds')
    parser.add_option('--set-interval', dest='setint', metavar='INTERVAL',
                      help='set logging interval, in seconds')
    (options, args) = parser.parse_args()

    if options.version:
        print "CC3000 driver version %s" % DRIVER_VERSION
        exit(0)

    if options.testcrc:
        _check_crc('OK')
        _check_crc('REC,2010/01/01 14:12, 64.5, 85,29.04,349,  2.4,  4.2,  0.00, 6.21, 0.25, 73.2,!B82C')
        _check_crc('MSG,2010/01/01 20:22,CHARGER ON,!4CED')
        exit(0)

    with CC3000(options.port) as s:
        if options.getver:
            print s.get_version()
        if options.status:
            print s.get_memory_status()
        if options.getcur:
            print s.get_current_data()
        if options.getrec:
            for r in s.get_records():
                print r
        if options.gethead:
            print s.get_header()
        if options.getunits:
            print s.get_units()
        if options.setunits:
            s.set_units(options.setunits)
        if options.gettime:
            print s.get_time()
        if options.settime:
            s.set_time()
        if options.getint:
            print s.get_interval()
        if options.setint:
            s.set_interval(int(options.setint))
