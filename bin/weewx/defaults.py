# coding: utf-8
#
#    Copyright (c) 2019-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#

"""Backstop defaults used in the absence of any other values."""

from __future__ import absolute_import
import weeutil.config

DEFAULT_STR = """# Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
# See the file LICENSE.txt for your rights.

# Where the skins reside, relative to WEEWX_ROOT
SKIN_ROOT = skins

# Where the generated reports should go, relative to WEEWX_ROOT
HTML_ROOT = public_html

# The database binding indicates which data should be used in reports.
data_binding = wx_binding

# Whether to log a successful operation
log_success = True

# Whether to log an unsuccessful operation
log_failure = False

# The following section determines the selection and formatting of units.
[Units]

    # The following section sets what unit to use for each unit group.
    # NB: The unit is always in the singular. I.e., 'mile_per_hour',
    # NOT 'miles_per_hour'
    [[Groups]]

        group_altitude     = foot                 # Options are 'foot' or 'meter'
        group_amp          = amp
        group_concentration= microgram_per_meter_cubed
        group_data         = byte
        group_degree_day   = degree_F_day         # Options are 'degree_F_day' or 'degree_C_day'
        group_deltatime    = second
        group_direction    = degree_compass
        group_distance     = mile                 # Options are 'mile' or 'km'
        group_energy       = watt_hour
        group_energy2      = watt_second
        group_length       = inch
        group_moisture     = centibar
        group_percent      = percent
        group_pressure     = inHg                 # Options are 'inHg', 'mmHg', 'mbar', or 'hPa'
        group_radiation    = watt_per_meter_squared
        group_rain         = inch                 # Options are 'inch', 'cm', or 'mm'
        group_rainrate     = inch_per_hour        # Options are 'inch_per_hour', 'cm_per_hour', or 'mm_per_hour'
        group_speed        = mile_per_hour        # Options are 'mile_per_hour', 'km_per_hour', 'knot', or 'meter_per_second'
        group_speed2       = mile_per_hour2       # Options are 'mile_per_hour2', 'km_per_hour2', 'knot2', or 'meter_per_second2'
        group_temperature  = degree_F             # Options are 'degree_F' or 'degree_C'
        group_uv           = uv_index
        group_volt         = volt
        group_volume       = gallon

        # The following are used internally and should not be changed:
        group_count        = count
        group_interval     = minute
        group_time         = unix_epoch
        group_elapsed      = second

    # The following section sets the formatting for each type of unit.
    [[StringFormats]]

        centibar           = %.0f
        cm                 = %.2f
        cm_per_hour        = %.2f
        degree_C           = %.1f
        degree_F           = %.1f
        degree_compass     = %.0f
        foot               = %.0f
        hPa                = %.1f
        hour               = %.1f
        inHg               = %.3f
        inch               = %.2f
        inch_per_hour      = %.2f
        km                 = %.1f
        km_per_hour        = %.0f
        km_per_hour2       = %.1f
        knot               = %.0f
        knot2              = %.1f
        mbar               = %.1f
        meter              = %.0f
        meter_per_second   = %.1f
        meter_per_second2  = %.1f
        mile               = %.1f
        mile_per_hour      = %.0f
        mile_per_hour2     = %.1f
        mm                 = %.1f
        mmHg               = %.1f
        mm_per_hour        = %.1f
        percent            = %.0f
        second             = %.0f
        uv_index           = %.1f
        volt               = %.1f
        watt_per_meter_squared = %.0f
        NONE               = "   N/A"

    # The following section sets the label to be used for each type of unit
    [[Labels]]

        centibar          = " cb"
        cm                = " cm"
        cm_per_hour       = " cm/h"
        degree_C          =   °C
        degree_F          =   °F
        degree_compass    =   °
        foot              = " feet"
        hPa               = " hPa"
        inHg              = " inHg"
        inch              = " in"
        inch_per_hour     = " in/h"
        km                = " km"
        km_per_hour       = " km/h"
        km_per_hour2      = " km/h"
        knot              = " knots"
        knot2             = " knots"
        mbar              = " mbar"
        meter             = " meter", " meters"
        meter_per_second  = " m/s"
        meter_per_second2 = " m/s"
        mile              = " mile", " miles"
        mile_per_hour     = " mph"
        mile_per_hour2    = " mph"
        mm                = " mm"
        mmHg              = " mmHg"
        mm_per_hour       = " mm/h"
        percent           =   %
        volt              = " V"
        watt_per_meter_squared = " W/m²"
        day               = " day",    " days"
        hour              = " hour",   " hours"
        minute            = " minute", " minutes"
        second            = " second", " seconds"
        NONE              = ""

    # The following section sets the format to be used for each time scale.
    # The values below will work in every locale, but they may not look
    # particularly attractive. See the Customization Guide for alternatives.
    [[TimeFormats]]

        hour       = %H:%M
        day        = %X
        week       = %X (%A)
        month      = %x %X
        year       = %x %X
        rainyear   = %x %X
        current    = %x %X
        ephem_day  = %X
        ephem_year = %x %X

    [[Ordinates]]

        # Ordinal directions. The last one should be for no wind direction
        directions = N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW, N/A

    # The following section sets the base temperatures used for the
    #  calculation of heating and cooling degree-days.
    [[[DegreeDays]]]

        # Base temperature for heating days, with unit:
        heating_base = 65, degree_F
        # Base temperature for cooling days, with unit:
        cooling_base = 65, degree_F
        # Base temperature for growing days, with unit:
        growing_base = 50, degree_F

    # A trend takes a difference across a time period. The following
    # section sets the time period, and how big an error is allowed to
    # still be counted as the start or end of a period.
    [[[Trend]]]

        time_delta = 10800  # 3 hours
        time_grace = 300    # 5 minutes

# The labels are applied to observations or any other strings.
[Labels]

    # Set to hemisphere abbreviations suitable for your location:
    hemispheres = N, S, E, W
    # Formats to be used for latitude whole degrees, longitude whole
    # degrees, and minutes:
    latlon_formats = "%02d", "%03d", "%05.2f"

    # Generic labels, keyed by an observation type.
    [[Generic]]
        barometer      = Barometer
        barometerRate  = Barometer Change Rate
        dewpoint       = Dew Point
        ET             = ET
        heatindex      = Heat Index
        inHumidity     = Inside Humidity
        inTemp         = Inside Temperature
        outHumidity    = Humidity
        outTemp        = Outside Temperature
        radiation      = Radiation
        rain           = Rain
        rainRate       = Rain Rate
        UV             = UV Index
        windDir        = Wind Direction
        windGust       = Gust Speed
        windGustDir    = Gust Direction
        windSpeed      = Wind Speed
        windchill      = Wind Chill
        windgustvec    = Gust Vector
        windvec        = Wind Vector
        windrun        = Wind Run
        extraTemp1     = Temperature1
        extraTemp2     = Temperature2
        extraTemp3     = Temperature3

        # Sensor status indicators

        rxCheckPercent       = Signal Quality
        txBatteryStatus      = Transmitter Battery
        windBatteryStatus    = Wind Battery
        rainBatteryStatus    = Rain Battery
        outTempBatteryStatus = Outside Temperature Battery
        inTempBatteryStatus  = Inside Temperature Battery
        consBatteryVoltage   = Console Battery
        heatingVoltage       = Heating Battery
        supplyVoltage        = Supply Voltage
        referenceVoltage     = Reference Voltage

[Almanac]

    # The labels to be used for the phases of the moon:
    moon_phases = New, Waxing crescent, First quarter, Waxing gibbous, Full, Waning gibbous, Last quarter, Waning crescent
"""

defaults = weeutil.config.config_from_str(DEFAULT_STR)
