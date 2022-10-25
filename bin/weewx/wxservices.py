#
#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Calculate derived variables, depending on software/hardware preferences.

While this is named 'StdWXCalculate' for historical reasons, it can actually calculate
non-weather related derived types as well.
"""
from __future__ import absolute_import

import logging

import weeutil.weeutil
import weewx.engine
import weewx.units

log = logging.getLogger(__name__)


class StdWXCalculate(weewx.engine.StdService):

    def __init__(self, engine, config_dict):
        """Initialize an instance of StdWXCalculate and determine the calculations to be done.

        Directives look like:

           obs_type = [prefer_hardware|hardware|software], [loop|archive]

        where:

        obs_type is an observation type to be calculated, such as 'heatindex'

        The choice [prefer_hardware|hardware|software] determines how the value is to be
        calculated. Option "prefer_hardware" means that if the hardware supplies a value, it will
        be used, otherwise the value will be calculated in software.

        The choice [loop|archive] indicates whether the calculation is to be done for only LOOP
        packets, or only archive records. If left out, it will be done for both.

        Examples:

            cloudbase = software,loop
        The derived type 'cloudbase' will always be calculated in software, but only for LOOP
        packets

            cloudbase = software, record
        The derived type 'cloudbase' will always be calculated in software, but only for archive
        records.

            cloudbase = software
        The derived type 'cloudbase' will always be calculated in software, for both LOOP packets
        and archive records"""

        super(StdWXCalculate, self).__init__(engine, config_dict)

        self.loop_calc_dict = dict()        # map {obs->directive} for LOOP packets
        self.archive_calc_dict = dict()     # map {obs->directive} for archive records

        for obs_type, rule in config_dict.get('StdWXCalculate', {}).get('Calculations', {}).items():
            # Ensure we have a list:
            words = weeutil.weeutil.option_as_list(rule)
            # Split the list up into a directive, and (optionally) which bindings it applies to
            # (loop or archive).
            directive = words[0].lower()
            bindings = [w.lower() for w in words[1:]]
            if not bindings or 'loop' in bindings:
                # no bindings mentioned, or 'loop' plus maybe others
                self.loop_calc_dict[obs_type] = directive
            if not bindings or 'archive' in bindings:
                # no bindings mentioned, or 'archive' plus maybe others
                self.archive_calc_dict[obs_type] = directive

        # Backwards compatibility for configuration files v4.1 or earlier:
        self.loop_calc_dict.setdefault('windDir', 'software')
        self.archive_calc_dict.setdefault('windDir', 'software')
        self.loop_calc_dict.setdefault('windGustDir', 'software')
        self.archive_calc_dict.setdefault('windGustDir', 'software')
        # For backwards compatibility:
        self.calc_dict = self.archive_calc_dict

        if weewx.debug > 1:
            log.debug("Calculations for LOOP packets: %s", self.loop_calc_dict)
            log.debug("Calculations for archive records: %s", self.archive_calc_dict)

        # Get the data binding. Default to 'wx_binding'.
        data_binding = config_dict.get('StdWXCalculate',
                                       {'data_binding': 'wx_binding'}).get('data_binding',
                                                                           'wx_binding')
        # Log the data binding we are to use
        log.info("StdWXCalculate will use data binding %s" % data_binding)
        # If StdArchive and StdWXCalculate use different data bindings it could
        # be a problem. Get the data binding to be used by StdArchive.
        std_arch_data_binding = config_dict.get('StdArchive', {}).get('data_binding',
                                                                      'wx_binding')
        # Is the data binding the same as will be used by StdArchive?
        if data_binding != std_arch_data_binding:
            # The data bindings are different, don't second guess the user but
            # log the difference as this could be an oversight
            log.warning("The StdWXCalculate data binding (%s) does not "
                        "match the StdArchive data binding (%s).",
                        data_binding, std_arch_data_binding)
        # Now obtain a database manager using the data binding
        self.db_manager = engine.db_binder.get_manager(data_binding=data_binding,
                                                       initialize=True)

        # We will process both loop and archive events
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.do_calculations(event.packet, self.loop_calc_dict)

    def new_archive_record(self, event):
        self.do_calculations(event.record, self.archive_calc_dict)

    def do_calculations(self, data_dict, calc_dict=None):
        """Augment the data dictionary with derived types as necessary.

        data_dict: The incoming LOOP packet or archive record.
        calc_dict: the directives to apply
        """

        if calc_dict is None:
            calc_dict = self.archive_calc_dict

        # Go through the list of potential calculations and see which ones need to be done
        for obs in calc_dict:
            # Keys in calc_dict are in unicode. Keys in packets and records are in native strings.
            # Just to keep things consistent, convert.
            obs_type = str(obs)
            if calc_dict[obs] == 'software' \
                    or (calc_dict[obs] == 'prefer_hardware' and data_dict.get(obs_type) is None):
                # We need to do a calculation for type 'obs_type'. This may raise an exception,
                # so be prepared to catch it.
                try:
                    val = weewx.xtypes.get_scalar(obs_type, data_dict, self.db_manager)
                except weewx.CannotCalculate:
                    # XTypes is aware of the type, but can't calculate it, probably because of
                    # missing data. Set the type to None.
                    data_dict[obs_type] = None
                except weewx.NoCalculate:
                    # XTypes is aware of the type, but does not need to calculate it.
                    pass
                except weewx.UnknownType as e:
                    log.debug("Unknown extensible type '%s'" % e)
                except weewx.UnknownAggregation as e:
                    log.debug("Unknown aggregation '%s'" % e)
                else:
                    # If there was no exception, then all is good. Convert to the same unit
                    # as the record...
                    new_value = weewx.units.convertStd(val, data_dict['usUnits'])
                    # ... then add the results to the dictionary
                    data_dict[obs_type] = new_value[0]

