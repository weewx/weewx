#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Calculate derived variables, depending on software/hardware preferences.

While this is named 'StdWXCalculate' for historical reasons, it can actually calculate
non-weather related derived types as well.
"""
from __future__ import absolute_import

import logging

import weewx.engine

log = logging.getLogger(__name__)


class StdWXCalculate(weewx.engine.StdService):

    def __init__(self, engine, config_dict):
        """Initialize an instance of StdWXXTypes"""
        super(StdWXCalculate, self).__init__(engine, config_dict)

        # Get the dictionary containing the calculations to be done. Default to no calculations
        self.calc_dict = config_dict.get('StdWXCalculate', {}).get('Calculations', {})

        # Backwards compatibility for configuration files v4.1 or earlier:
        self.calc_dict.setdefault('windDir', 'software')
        self.calc_dict.setdefault('windGustDir', 'software')

        # Get the data binding. Default to 'wx_binding'.
        data_binding = config_dict.get('StdWXCalculate',
                                       {'data_binding': 'wx_binding'}).get('data_binding',
                                                                           'wx_binding')

        self.db_manager = engine.db_binder.get_manager(data_binding=data_binding, initialize=True)

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet)

    def new_archive_record(self, event):
        self.do_calculations(event.record)

    def do_calculations(self, data_dict):
        """Augment the data dictionary with derived types as necessary.

        data_dict: The incoming LOOP packet or archive record.
        """

        # Go through the list of potential calculations and see which ones need to be done
        for obs in self.calc_dict:
            directive = self.calc_dict[obs]
            # Keys in calc_dict are in unicode. Keys in packets and records are in native strings.
            # Just to keep things consistent, convert.
            obs_type = str(obs)
            if directive == 'software' or directive == 'prefer_hardware' \
                    and (obs_type not in data_dict or data_dict[obs_type] is None):
                try:
                    # We need to do a calculation for type 'obs_type'. This may raise an exception.
                    new_value = weewx.xtypes.get_scalar(obs_type, data_dict, self.db_manager)
                except weewx.CannotCalculate:
                    pass
                except weewx.UnknownType as e:
                    log.debug("Unknown extensible type '%s'" % e)
                except weewx.UnknownAggregation as e:
                    log.debug("Unknown aggregation '%s'" % e)
                else:
                    # If there was no exception, add the results to the dictionary
                    data_dict[obs_type] = new_value[0]

