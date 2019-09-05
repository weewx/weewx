#
#    Copyright (c) 2009-2018 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""User-defined, extended types"""
from __future__ import print_function

import itertools

import six

import weewx.units
import weewx.wxformulas
import weewx.uwxutils


class ExtendedTypes(dict):

    def __init__(self, record, new_types={}):
        # Initialize my super class...
        super(ExtendedTypes, self).__init__(record)
        # ... then a dictionary of new types.
        self.new_types = new_types

    def __len__(self):
        return dict.__len__(self) + len(self.new_types)

    def __iter__(self):
        # Chain together my superclass's iterator, and an iterator over the new types
        return itertools.chain(dict.__iter__(self), iter(self.new_types))

    def __getitem__(self, key):
        if key in self.new_types:
            return self.new_types[key](key, self)
        return dict.__getitem__(self, key)

    def __delitem__(self, key):
        if key in self.new_types:
            del self.new_types[key]
        else:
            dict.__delitem__(self, key)

    def __contains__(self, key):
        return key in self.new_types or dict.__contains__(self, key)

    def keys(self):
        return itertools.chain(self.new_types.keys(), dict.keys(self))

    def items(self):
        return itertools.chain(self.new_types.items().dict.items(self))

    def iteritems(self):
        return itertools.chain(six.iteritems(self.new_types), six.iteritems(super(ExtendedTypes, self)))

    def iterkeys(self):
        return itertools.chain(self.new_types.iterkeys(), dict.iterkeys(self))

    def itervalues(self):
        return itertools.chain(self.new_types.itervalues(), dict.itervalues(self))

    def values(self):
        raise NotImplementedError

    def get(self, key, default=None):
        if key in self.new_types:
            return self.new_types[key](key, self)
        return dict.get(self, key, default)


class PressureCooker(object):
    """Do calculations relating to barometric pressure"""

    def __init__(self, altitude_ft, dbmanager, max_ts_delta=1800):
        self.altitude_ft = altitude_ft
        self.dbmanager = dbmanager
        self.max_ts_delta = max_ts_delta
        # Timestamp (roughly) 12 hours ago
        self.ts_12h = None
        # Temperature 12 hours ago in Fahrenheit
        self.temp_12h_F = None

    def _get_temperature_12h_F(self, ts):
        """Get the temperature in Fahrenheit from 12 hours ago.  The value will
         be None if no temperature is available."""

        ts_12h = ts - 12 * 3600

        # Look up the temperature 12h ago if this is the first time through,
        # or we don't have a usable temperature, or the old temperature is too stale.
        if self.ts_12h is None or self.temp_12h_F is None or abs(self.ts_12h - ts_12h) < self.max_ts_delta:
            # Hit the database to get a newer temperature
            record = self.dbmanager.getRecord(ts_12h, max_delta=self.max_ts_delta)
            temperature = record.get('outTemp') if record else None
            # Convert to Fahrenheit if necessary
            if temperature is not None and record['usUnits'] & 0x10:
                # One of the metric systems (METRIC or METRICWX) is being used. Convert.
                temperature = weewx.units.CtoF(temperature)
            # Save the temperature and timestamp
            self.temp_12h_F = temperature
            self.ts_12h = ts_12h

        # Return in F
        return self.temp_12h_F

    def calc(self, key, record):
        if key == 'pressure':
            return self.calc_pressure(record)

    def calc_pressure(self, record):
        # The following requires everything to be in US Customary units
        record_US = weewx.units.to_US(record)
        # Get the temperature in Fahrenheit from 12 hours ago
        temp_12h_F = self._get_temperature_12h_F(record['dateTime'])
        if temp_12h_F is not None:
            try:
                pressure = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                    record_US['barometer'],
                    self.altitude_ft,
                    record_US['outTemp'],
                    temp_12h_F,
                    record_US['outHumidity']
                )
            except KeyError:
                return None
        else:
            return None
        pressure_vt = weewx.units.ValueTuple(pressure, "inHg", "group_pressure")
        # Convert to the same unit system used by the incoming record
        pressure_final = weewx.units.convertStd(pressure_vt, record['usUnits'])
        return pressure_final[0]
