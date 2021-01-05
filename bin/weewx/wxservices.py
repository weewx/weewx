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

        # determine the calculations to be done and when
        #
        # create calc_dicts for LOOP and for ARCHIVE holding the calculations
        # to be done at those times. the configuration indicates the bindings,
        # and thus into which or both calc_dicts that each calculation should
        # be placed. no bindings mentioned means 'loop' and 'archive' e.g.
        # 'cloudbase = software' same as 'cloudbase = software,loop,archive'
        # (backwards compatability with weewx 4.2 configuration files).
        # TODO document in User and/or Customisation Guide
        #
        # Default to no calculations.
        #
        self.loop_calc_dict = dict()        # map {obs->directive} for LOOP
        self.archive_calc_dict = dict()     # map {obs->directive} for ARCHIVE
        for obs, rule in config_dict.get('StdWXCalculate', {}).get('Calculations', {}).items():
            # ensure we have a list, not a (possibly comma-separated) string
            words = rule if isinstance(rule, list) else rule.split(',')
            # canonicalise to trimmed lower case
            words = [w.strip().lower() for w in words]

            # the first word is the directive, the rest are bindings (if any)
            if len(words) == 1 or 'loop' in words:
                # no bindings mentioned, or 'loop' plus maybe others
                self.loop_calc_dict[obs] = words[0]
            if len(words) == 1 or 'archive' in words:
                # no bindings mentioned, or 'archive' plus maybe others
                self.archive_calc_dict[obs] = words[0]

        # Backwards compatibility for configuration files v4.1 or earlier:
        self.loop_calc_dict.setdefault('windDir', 'software')
        self.archive_calc_dict.setdefault('windDir', 'software')
        self.loop_calc_dict.setdefault('windGustDir', 'software')
        self.archive_calc_dict.setdefault('windGustDir', 'software')

        if weewx.debug > 1:
            log.debug(f"Calculations for LOOP: {self.loop_calc_dict}")
            log.debug(f"Calculations for ARCHIVE: {self.archive_calc_dict}")

        # Get the data binding. Default to 'wx_binding'.
        data_binding = config_dict.get('StdWXCalculate',
                                       {'data_binding': 'wx_binding'}).get('data_binding',
                                                                           'wx_binding')

        self.db_manager = engine.db_binder.get_manager(data_binding=data_binding, initialize=True)

        # we will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, self.loop_calc_dict)

    def new_archive_record(self, event):
        self.do_calculations(event.record, self.archive_calc_dict)

    def do_calculations(self, data_dict, calc_dict):
        """Augment the data dictionary with derived types as necessary.

        data_dict: The incoming LOOP packet or archive record.
        calc_dict: the directives to apply
        """

        # Go through the list of potential calculations and see which ones need to be done
        for obs in calc_dict:
            directive = calc_dict[obs]
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

