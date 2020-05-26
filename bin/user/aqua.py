# Copyright (c) 2015-20 Graham Eddy <graham.eddy@gmail.com>
# Distributed under the terms of the GNU Public License (GPLv3)
"""
aqua module provides weewx data service.
pseudo-driver for aquagauge controller, which supports up to 8 wireless sensors,
that inserts its values into next LOOP record

weewx.conf configuration:
[Aquagauge]
    port = /dev/ttyUSB0         # serial port device; no default
    speed = 2400                # baud; port speed; default=2400
    open_attempts_max = 4       # max no open attempts; default=4
    open_attempts_delay = 2     # secs; delay before re-open; default=2
    open_attempts_delay_long = 1800 # secs; long attempts delay; default=1800
        # if opening port fails, retry open up to {open_attempts_max} times,
        # with {open_attempts_delay} secs between attempts. if even this fails,
        # back off for a further {open_attempts_delay_long} secs before trying
        # all over again. keep trying until port open succeeds.
        # read failure is handled by closing and re-opening the port.
    [[ 0 ]]                     # sensor #0; default=disabled
        data_type = outTemp     # data_type in LOOP record to be written
        unit = degree_C         # unit of driver's provided value; default=raw
    [[ 1 ]] ...                 # up to sensor #7...
        # at least one sensor must be enabled i.e. have {data_type} defined
        # otherwise the service exits.
        # service also exits if a mandatory config parameter is absent or
        # any provided config parameter is invalid

key implementation notes:
  * port i/o confined to its own, separate thread
"""

import sys
if sys.version_info[0] < 3:
    raise ImportError("requires python3")
import queue
import logging
import serial
import threading
import time

import weewx
import weewx.units
from weewx.engine import StdService

log = logging.getLogger(__name__)
version = "3.0"


class AquagaugeSvc(StdService):
    """service that inserts data from Aquagauge controller into LOOP packets"""

    def __init__(self, engine, config_dict):
        super(AquagaugeSvc, self).__init__(engine, config_dict)

        # noinspection PyUnusedLocal
        aqua = None
        try:                        # set up
            log.info(f"{self.__class__.__name__}: starting (version {version})")

            # configuration
            # noinspection PyUnusedLocal
            port = None
            # noinspection PyUnusedLocal
            speed = None
            # noinspection PyUnusedLocal
            open_attempts_max = None
            # noinspection PyUnusedLocal
            open_attempts_delay = None
            # noinspection PyUnusedLocal
            open_attempts_delay_long = None
            self.data_types = None  # data_type, indexed by sensor_id
            self.units = None       # units, indexed by sensor_id
            try:
                aqua_dict = config_dict['Aquagauge']    # mandatory

                # per-controller parameters
                port = aqua_dict['port']           # mandatory
                speed = int(aqua_dict.get('speed', 2400))
                open_attempts_max = int(aqua_dict.get('open_attempts_max', 4))
                open_attempts_delay = float(aqua_dict.get('open_attempts_delay', 2.0))
                open_attempts_delay_long = float(aqua_dict.get('open_attempts_delay_long', 1800.0))

                # per-sensor parameters
                self.data_types = [None for _i in range(Aquagauge.MAX_SENSORS)]
                self.units = self.data_types[:]
                sensor_count = 0
                for sensor_id, sensor_dict in aqua_dict.items():
                    if isinstance(sensor_dict, dict):
                        sensor_id = int(sensor_id)
                        if 'data_type' in sensor_dict:
                            self.data_types[sensor_id] = sensor_dict['data_type']
                            sensor_count += 1
                        if 'unit' in sensor_dict:
                            self.units[sensor_id] = sensor_dict['unit']
                if sensor_count <= 0:
                    log.error(f"{self.__class__.__name__}: no sensors enabled")
                    raise RuntimeError("no sensors")

            # handle configuration error
            except KeyError as e:
                log.error(f"{self.__class__.__name__}: config: lacking {e.args[0]}")
                raise
            except (ValueError, TypeError) as e:
                log.error(f"{self.__class__.__name__}: config: bad value {e.args[0]}")
                raise
            except IndexError:
                log.error(f"{self.__class__.__name__}: config: bad sensor_id")
                raise

            # spawn acquirer thread
            self.q = queue.Queue()
            aqua = Aquagauge(port, speed, open_attempts_max,
                             open_attempts_delay, open_attempts_delay_long)
            try:
                t = threading.Thread(target=aqua.run, args=(self.q,))
                t.start()
            except threading.ThreadError as e:
                log.error(f"{self.__class__.__name__}: thread failed: {repr(e)}")
                raise

            # start listening to new packets
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_record)
            # self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            log.info(f"{self.__class__.__name__} started (version {version}):"
                     f" {sensor_count} sensors enabled")

        except (IndexError, KeyError, RuntimeError, TypeError, ValueError,
                threading.ThreadError):
            log.error(f"{self.__class__.__name__}: not started (version {version})")

    def new_loop_record(self, event):
        """handle LOOP record by inserting queued readings"""

        count = 0
        try:
            while not self.q.empty():
                reading = self.q.get(block=False)
                self.update(reading, event.packet)  # over-write prior is unlikely but ok
                self.q.task_done()
                count += 1
        except queue.Empty:
            log.debug(f"{self.__class__.__name__}: queue.Empty")
            pass        # corner case that can be ignored
        if count > 0:
            log.info(f"{self.__class__.__name__}: {count} readings found")
        else:
            log.debug(f"{self.__class__.__name__}: {count} readings found")

#    def new_archive_record(self, event):
#        """handle ARCHIVE record by ..."""
#        ...handle...(event.record)

    def update(self, reading, packet):
        """apply a reading to the packet"""

        # update LOOP packet where sensor is enabled and has a value
        for sensor_id, value in enumerate(reading):
            if value is not None and self.data_types[sensor_id]:
                if self.units[sensor_id]:
                    # convert to internal units
                    unit_group = weewx.units.obs_group_dict[self.data_types[sensor_id]]
                    vt = weewx.units.ValueTuple(value, self.units[sensor_id], unit_group)
                    vh = weewx.units.ValueHelper(vt,
                        converter=weewx.units.StdUnitConverters[weewx.US])
                    value = vh.raw
                # insert value into packet
                log.debug(f"{self.__class__.__name__}.update packet["
                          f"{self.data_types[sensor_id]}]={value}")
                packet[self.data_types[sensor_id]] = value


class Aquagauge:

    # a reading is a list of observed values, indexed by sensor_id
    #
    # number of sensors supported by controller
    MAX_SENSORS = 8

    # input records are formatted as
    #   reading ::= [ key value ]* "i"
    #   key ::= "a"|"b"|"c"|"d"|"e"|"f"|"g"|"h"
    #   value ::= digit [ digit ]*
    #   digit ::= "0"|"1"|"2"|"3"|"4"|"5"|"6"|"7"|"8"|"9"
    # where
    #   key is sensor_id offset by "a" e.g. c -> 2
    #   value is positive decimal integer
    #   there is no white space
    KEYS = b'abcdefgh'
    END_KEY = b'i'
    DIGITS = b'0123456789'

    def __init__(self, port, speed, open_attempts_max,
                 open_attempts_delay, open_attempts_delay_long):

        self.port = port
        self.speed = speed
        self.open_attempts_max = open_attempts_max
        self.open_attempts_delay = open_attempts_delay
        self.open_attempts_delay_long = open_attempts_delay_long

        self.f = None

    def run(self, q):
        """insert readings from Aquagauge driver onto queue"""

        ch = self.getc()
        while True:             # process all records
            reading = [None for _i in range(Aquagauge.MAX_SENSORS)]

            while True:         # process all fields of one record

                # check for completion of a record
                if ch == Aquagauge.END_KEY:
                    q.put(reading)
                    ch = self.getc()
                    break       # record finished

                # identify key
                if ch not in Aquagauge.KEYS:
                    log.warning(f"{self.__class__.__name__}: invalid key {ch}")
                    ch = self.getc()
                    continue    # field finished (failed)
                sensor_id = Aquagauge.KEYS.index(ch)
                ch = self.getc()

                # calculate value
                if ch not in Aquagauge.DIGITS:
                    log.warning(f"{self.__class__.__name__}: missing value")
                    continue    # field finished (failed)
                value = Aquagauge.DIGITS.index(ch)
                while True:
                    ch = self.getc()
                    if ch not in Aquagauge.DIGITS:
                        break   # value finished (success)
                    value = 10*value + Aquagauge.DIGITS.index(ch)
                reading[sensor_id] = value

    def getc(self):
        """get next char, in robust fashion"""

        # open device if not already open
        if self.f is None:
            self.open()

        # try to read next char
        try:
            ch = self.f.read(1)
            if ch:
                return ch       # finished (success)
            # EOF, so drop through to error recovery
            log.warning(f"{self.__class__.__name__}: EOF")
        except serial.SerialException as e:
            log.error(f"{self.__class__.__name__}: read error", exc_info=e)

        # error recovery = close device and allow it to be re-opened
        try:
            self.f.close()
        except serial.SerialException as e:
            log.error(f"{self.__class__.__name__}: close error", exc_info=e)
        self.f = None

    def open(self):
        """open device, in robust fashion"""

        while True:             # try forever...

            # have a few short attempts
            for attempt in range(self.open_attempts_max):
                try:
                    # 8 bits, 1 stop bit, no parity, no xon/xoff, no rts/dtr
                    self.f = serial.Serial(port=self.port, baudrate=self.speed)
                    log.debug(f"{self.__class__.__name__}: {self.port}: open succeeded")
                    return      # finished open (success)
                except ValueError as e:
                    log.error(f"{self.__class__.__name__}: bad port config: {repr(e)}")
                except serial.SerialException as e:
                    log.error(f"{self.__class__.__name__}: {e.args[1]}")
                time.sleep(self.open_attempts_delay)

            # have a long delay and hope for external intervention
            log.warning(f"{self.__class__.__name__}: long sleep"
                        f" waiting for port problem to be cleared")
            time.sleep(self.open_attempts_delay_long - self.open_attempts_delay)
