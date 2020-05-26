# Copyright 2019-2020 Graham Eddy <graham.eddy@gmail.com>
# Distributed under the terms of the GNU Public License (GPLv3)
# weewx:
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your full rights.
"""
jammer module provides weewx services that jam data into LOOP/ARCHIVE packets.

The target field can be one already existing in the packet (overwriting it)
or a new field. The most useful case is using an existing field in ARCHIVE
packet that is written to weewx database - this obviates the need to extend
weewx schema.

------------------------------------------------------------------------------
DriverJammer
provides weewx service that jams data into LOOP/ARCHIVE packets
from other fields within that packet.

* Each datum is sourced from another field in packet (usually provided by
  the driver).
* The datum value is considered not available if source field in packet is
  not found, and target field is set to None (not absent from packet).
* Datum value is updated in each LOOP and ARCHIVE packet
* Configuration parameters:
      [[dest]]    mandatory    packet field to be overwritten
      source      mandatory    packet field whose value is used to overwrite

example of configuration via weewx.conf:
    [DriverJammer]
      [[soilMoist2]]           # 'soilmoist2' data_type to be overwritten
                               #   in all LOOP and ARCHIVE records
        source = stormRain     # 'stormRain' data_type value to be used
      [[leafWet2]]             # 'leafWet2' data_type to be overwritten
                               #   in all LOOP and ARCHIVE packets.
        source = forecastRule  # 'forecastRule' data_type value to be used.

------------------------------------------------------------------------------
FileJammer
provides weewx service that jams data into LOOP/ARCHIVE packets from a file.

* The external datum is provided in a file, which has a single line with
  timestamp (unix epoch) space-separated from datum value.
* The datum value is considered not available if too old (expired) or
  inaccessible (file open failure), and is set to None (but not absent
  from packet).
* The file is always read and jammed into ARCHIVE packets. Optionally, it
  can do same for LOOP packets. If it is not re-read for each LOOP packet
  then the most recent ARCHIVE value is carried forward into each LOOP
  packet
* The jammed value needs to be in US units. It needs to be converted if not.
* Configuration parameters:
      [[data_type]]  mandatory  packet field to be overwritten
      file           mandatory  file containing epoch/value pair
      units          optional   the units of the value in the file e.g.
                                mm. This allows conversion to weewx
                                internal format, US inch (default: naked
                                value used)
      is_loop        optional   re-read file for each LOOP packet, else
                                just carry last ARCHIVE value into LOOP
                                packets (default: false)
      expiry         optional   data older than this many minutes is
                                invalid, use value NULL instead
                                (default: 60 mins)

example of configuration via weewx.conf:
    [FileJammer]
      [[soilTemp2]]     # data_type is 'soilTemp2' in packet.
        file = /opt/aquagauge/var/riverlevel.txt # file with epoch/value.
        units = mm      # convert value in file from mm to inch.
                        # no 'is_loop' so file read for ARCHIVE packets
                        #   only, value re-used in subsequent LOOP packets.
        expiry = 30     # expiry is 30 mins.
      [[soilTemp3]]     # data_type is 'soilTemp3' in packet.
        file = /opt/aquagauge/var/riverspeed.txt # file with epoch/value.
                        # no 'units' so raw value used (assumed US)
        is_loop = True  # file also re-read for every LOOP packet.
                        # no 'expiry' so expiry is 60 mins.
where /opt/aquagauge/var/riverlevel.txt might contain
    1577266515.24 33.6666666667
"""

import logging

import weewx
import weewx.units
from weewx.engine import StdService
from weeutil.weeutil import to_float, to_bool

log = logging.getLogger(__name__)
version = "1.3"


class DriverJammer(StdService):

    def __init__(self, engine, config_dict):
        super(DriverJammer, self).__init__(engine, config_dict)
        log.debug(f"{self.__class__.__name__} starting")

        # instance attributes
        self.sources = {}         # dict of dest data_type -> source data_type

        # configuration
        for dest, dest_dict in \
                config_dict.get(self.__class__.__name__, {}).items():
            if 'source' not in dest_dict:
                log.warning(f"{self.__class__.__name__}: {dest}: source missing")
                continue  # carry on without this dest
            self.sources[dest] = dest_dict['source']

        if not self.sources:
            log.error(f"{self.__class__.__name__} not started: no entries")
            return      # just slip away without binding to any listeners...

        # start listening to new packets
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info(f"{self.__class__.__name__} started: {len(self.sources)} entries")

    def new_loop_packet(self, event):
        """jam into the new LOOP packet"""
        self.jam(event.packet)

    def new_archive_record(self, event):
        """jam the new ARCHIVE record"""
        self.jam(event.record)

    def jam(self, packet):
        """jam source fields into dest fields in packet"""

        for dest, source in self.sources.items():
            if source not in packet:
                log.debug(f"{self.__class__.__name__}: {dest}: {source} missing")
                packet[dest] = None
                continue
            packet[dest] = packet[source]


class FileJammer(StdService):

    def __init__(self, engine, config_dict):
        super(FileJammer, self).__init__(engine, config_dict)

        log.debug(f'{self.__class__.__name__} starting')

        # instance attributes
        self.files = {}         # dict of dest -> filename
        self.is_loop = {}       # dict of dest -> LOOP enabled
        self.expiries = {}      # dict of dest -> expiry periods
        self.units = {}         # dict of dest -> unit of measure
        self.last_values = {}   # dict of dest -> last file value

        # configuration
        for dest, dest_dict in config_dict.get(self.__class__.__name__, {}).items():

            # 'file' is mandatory for a data_type
            if 'file' not in dest_dict:
                log.warning(f"{self.__class__.__name__}: dest {dest}:"
                            f" file missing")
                continue  # carry on without this data_type
            self.files[dest] = dest_dict['file']

            # the other parameters are optional
            try:
                self.units[dest] = dest_dict.get('units', None)
                self.is_loop[dest] = to_bool(dest_dict.get('loop', False))
                self.expiries[dest] = to_float(dest_dict.get('expiry', 60))
                self.expiries[dest] *= 60  # mins->secs
            except ValueError as e:
                log.warning(f"{self.__class__.__name__}: dest {dest}: {e.args[0]}")
                del self.files[dest]       # ignore this dest
                continue                   # carry on

            # no last value to remember yet...
            self.last_values[dest] = None

        if not self.files:
            log.error(f"{self.__class__.__name__} not started: no entries")
            return      # just slip away without binding to any listeners...

        # start listening to new packets
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info(f"{self.__class__.__name__} started: {len(self.files)} entries")

    def new_loop_packet(self, event):
        """jam into the new LOOP packet"""
        self.jam(event.packet, False)

    def new_archive_record(self, event):
        """jam into the new ARCHIVE record"""
        self.jam(event.record, True)

    def jam(self, packet, is_archive):
        """jam into any type of packet"""
        # the value to jam is either from the external file (if an ARCHIVE
        # packet or is_loop is set) or carried forward from last value

        # for all the jams, get the value from the file if so required
        for dest, filename in self.files.items():
            if is_archive or self.is_loop[dest]:

                # assume None unless persuaded otherwise
                self.last_values[dest] = None

                # extract values from file
                try:
                    with open(filename, 'r') as f:
                        epoch, value = f.readline().split()
                except IOError as e:
                    log.warning(f"{self.__class__.__name__}: {filename}: {e.args[0]}")
                    continue    # skip this jam

                # typecast the values
                try:
                    epoch = float(epoch)
                    value = float(value)
                except ValueError as e:
                    log.warning(f"{self.__class__.__name__}: {filename}: {e.args[0]}")
                    continue    # skip this jam

                # skip expiries
                if epoch + self.expiries[dest] < packet['dateTime']:
                    log.warning(f"{self.__class__.__name__}: {filename}: expired")
                    continue    # skip this jam

                # convert value if required
                if self.units[dest]:
                    try:
                        unit_group = weewx.units.obs_group_dict[dest]
                        vt = weewx.units.ValueTuple(value, self.units[dest], unit_group)
                        vh = weewx.units.ValueHelper(vt,
                            converter=weewx.units.StdUnitConverters[weewx.US])
                        value = vh.raw
                    except KeyError as e:
                        log.error(f"{self.__class__.__name__}: {dest}: {e.args[0]} missing")
                        continue    # skip this jam

                # if we get here, we have a proper value
                self.last_values[dest] = value

        # for all the jams, jam that value into the packet
        for dest, last_value in self.last_values.items():
            packet[dest] = last_value
