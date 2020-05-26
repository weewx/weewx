# Copyright (c) 2015-20 Graham Eddy <graham.eddy@gmail.com>
# Distributed under the terms of the GNU Public License (GPLv3)
"""
sedge module provides weewx data service.
pseudo-driver for solaredge inverter data uploaded into cloud by vendor
and inserts its values into next LOOP record

weewx.conf configuration:
[SolarEdge]
    api_key = your_api_key_from_vendor          # no default
    site_id = your_site_id_from_installer       # no default
    data_type = LOOP_packet_data_type           # no default

key implementation notes:
  * only generated solar energy is fetched
  * polling period is hard-coded to 15 minutes due to api limitations
"""

import sys
if sys.version_info[0] < 3:
    raise ImportError("requires python3")
import queue
import logging
import requests
import threading
import time

import weewx
import weewx.units
from weewx.engine import StdService

log = logging.getLogger(__name__)
version = "2.0"


class SolarEdgeSvc(StdService):
    """service that inserts data from SolarEdge cloud into LOOP packets"""

    def __init__(self, engine, config_dict):
        super(SolarEdgeSvc, self).__init__(engine, config_dict)

        # noinspection PyUnusedLocal
        sedge = None
        try:                        # set up
            log.info(f"{self.__class__.__name__}: starting (version {version})")

            # configuration
            # noinspection PyUnusedLocal
            api_key = None
            # noinspection PyUnusedLocal
            site_id = None
            # noinspection PyUnusedLocal
            self.data_type = None
            # noinspection PyUnusedLocal
            try:
                sedge_dict = config_dict['SolarEdge']   # mandatory

                # per-controller parameters
                api_key = sedge_dict['api_key']         # mandatory
                site_id = sedge_dict['site_id']       # mandatory
                self.data_type = sedge_dict['data_type']  # mandatory

            # handle configuration error
            except KeyError as e:
                log.error(f"{self.__class__.__name__}: config: lacking {e.args[0]}")
                raise

            # spawn acquirer thread
            self.q = queue.Queue()
            sedge = SolarEdge(api_key, site_id)
            try:
                t = threading.Thread(target=sedge.run, args=(self.q,))
                t.start()
            except threading.ThreadError as e:
                log.error(f"{self.__class__.__name__}: thread failed: {repr(e)}")
                raise

            # start listening to new packets
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_record)
            # self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            log.info(f"{self.__class__.__name__} started (version {version})")

        except (KeyError, threading.ThreadError):
            log.error(f"{self.__class__.__name__}: not started (version {version})")

    def new_loop_record(self, event):
        """handle LOOP record by inserting queued readings"""

        count = 0
        try:
            while not self.q.empty():
                reading = self.q.get(block=False)
                self.update(reading, event.packet)
                self.q.task_done()
                count += 1
        except queue.Empty:
            log.debug(f"{self.__class__.__name__}: queue.Empty")
            pass        # corner case that can be ignored
        if count > 0:
            log.info(f"{self.__class__.__name__}: {count} readings found")
        else:
            log.debug(f"{self.__class__.__name__}: {count} readings found for LOOP")

#    def new_archive_record(self, event):
#        """handle ARCHIVE record by ..."""
#        ...handle...(event.record)

    def update(self, reading, packet):
        """apply a reading to the packet"""

        # convert to internal units
        vt = weewx.units.ValueTuple(reading, 'watt_hour', 'group_energy')
        vh = weewx.units.ValueHelper(vt, converter=weewx.units.StdUnitConverters[weewx.US])

        # insert value into packet
        log.debug(f"{self.__class__.__name__} packet[{self.data_type}]={vh.raw}")
        packet[self.data_type] = vh.raw


class SolarEdge:

    API_URL = 'http://monitoringapi.solaredge.com'
    QTR_HOUR = 900  # secs

    def __init__(self, api_key, site_id):
        self.api_key = api_key
        self.site_id = site_id

    def run(self, q):
        """insert readings from SolarEdge cloud onto queue"""
        log.debug(f"{self.__class__.__name__} start")

        next_time = time.time()     # time scheduled for next update; starts now
        last_time = next_time - SolarEdge.QTR_HOUR  # time of last success
        while True:                 # forever...
            pkg = None
            try:
                # fetch energy readings for interval since last success
                pkg = self.get_energy_details(last_time, next_time)
            except requests.exceptions.RequestException as e:
                log.error(f"{self.__class__.__name__}: {repr(e)}")

            if pkg:
                try:
                    # sum the energy quantities in the interval since last success
                    total = 0.0
                    count = 0
                    log.debug(f"{self.__class__.__name__}: #readings="
                              f"{len(pkg['energyDetails']['meters'][0]['values'])}")
                    for reading in pkg['energyDetails']['meters'][0]['values']:
                        if 'value' in reading:  # api leaves out zero reading values
                            log.debug(f"{self.__class__.__name__}: value={reading['value']}")
                            epoch = SolarEdge.date2epoch(reading['date'])
                            if epoch < last_time:
                                # api often inserts readings from earlier than start
                                log.debug(f"{self.__class__.__name__}: skipped earlier")
                                continue
                            total += float(reading['value'])
                            count += 1
                        else:
                            log.debug(f"{self.__class__.__name__}: no value in reading")

                    # scale to watt-hours
                    scale = 1 if pkg['energyDetails']['unit'] == 'Wh' else 1000
                    total *= scale
                except KeyError as e:
                    log.warning(f"{self.__class__.__name__}: reading missing key: {e.args[0]}")
                except ValueError as e:
                    log.warning(f"{self.__class__.__name__}: reading: {e.args[0]}")
                else:
                    if count > 0:
                        # successfully found a reading
                        log.debug(f"{self.__class__.__name__}: put total={total}")
                        q.put(total)
                        last_time = next_time
                    else:
                        log.debug(f"{self.__class__.__name__}: no sum to put")

            # schedule next reading
            while True:
                next_time += SolarEdge.QTR_HOUR
                if next_time > time.time() + 5.0:
                    break       # min 5 secs sleep!
            time.sleep(next_time - time.time())

    @staticmethod
    def epoch2date(epoch):
        """convert UNIX epoch time to SolarEdge date format"""
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))

    @staticmethod
    def date2epoch(date):
        """convert SolarEdge date format to UNIX epoch time"""
        return time.mktime(time.strptime(date, '%Y-%m-%d %H:%M:%S'))

    def get_energy_details(self, start_time, end_time):
        # request energy readings for specified time interval
        log.debug(f"{self.__class__.__name__}.get start={start_time} end={end_time}")

        response = requests.get(
            f'{SolarEdge.API_URL}/site/{self.site_id}/energyDetails',
            params={
                'startTime': SolarEdge.epoch2date(start_time),
                'endTime': SolarEdge.epoch2date(end_time),
                'timeUnit': 'QUARTER_OF_AN_HOUR',
                'api_key': self.api_key
            })
        response.raise_for_status()

        readings = response.json()
        log.debug(f"{self.__class__.__name__}.get_energy_details readings={readings}")
        return readings
