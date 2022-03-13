# coding: utf-8
#
#    Copyright (c) 2019-2021 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#

"""Backstop defaults used in the absence of any other values."""

from __future__ import absolute_import
import weeutil.config

DEFAULT_STR = """# Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
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
        group_db           = dB
        group_degree_day   = degree_F_day         # Options are 'degree_F_day' or 'degree_C_day'
        group_deltatime    = second
        group_direction    = degree_compass
        group_distance     = mile                 # Options are 'mile' or 'km'
        group_energy       = watt_hour
        group_energy2      = watt_second
        group_fraction     = ppm
        group_illuminance  = lux
        group_length       = inch
        group_moisture     = centibar
        group_percent      = percent
        group_power        = watt
        group_pressure     = inHg                 # Options are 'inHg', 'mmHg', 'mbar', or 'hPa'
        group_pressure_rate= inHq_per_hour
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
        group_boolean      = boolean
        group_count        = count
        group_elapsed      = second
        group_interval     = minute
        group_time         = unix_epoch

    # The following section sets the formatting for each type of unit.
    [[StringFormats]]

        amp                = %.1f
        bit                = %.0f
        boolean            = %d
        byte               = %.0f
        centibar           = %.0f
        cm                 = %.2f
        cm_per_hour        = %.2f
        count              = %d
        cubic_foot         = %.1f
        day                = %.1f
        dB                 = %.0f
        degree_C           = %.1f
        degree_C_day       = %.1f
        degree_compass     = %.0f
        degree_E           = %.1f
        degree_F           = %.1f
        degree_F_day       = %.1f
        degree_K           = %.1f
        foot               = %.0f
        gallon             = %.1f
        hour               = %.1f
        hPa                = %.1f
        hPa_per_hour       = %.3f
        inch               = %.2f
        inch_per_hour      = %.2f
        inHg               = %.3f
        inHg_per_hour      = %.5f
        kilowatt           = %.1f
        kilowatt_hour      = %.1f
        km                 = %.1f
        km_per_hour        = %.0f
        km_per_hour2       = %.1f
        knot               = %.0f
        knot2              = %.1f
        kPa                = %.2f
        kPa_per_hour       = %.4f
        liter              = %.1f
        litre              = %.1f
        lux                = %.0f
        mbar               = %.1f
        mbar_per_hour      = %.4f
        mega_joule         = %.0f
        meter              = %.0f
        meter_per_second   = %.1f
        meter_per_second2  = %.1f
        microgram_per_meter_cubed = %.0f
        mile               = %.1f
        mile_per_hour      = %.0f
        mile_per_hour2     = %.1f
        minute             = %.1f
        mm                 = %.1f
        mm_per_hour        = %.1f
        mmHg               = %.1f
        mmHg_per_hour      = %.4f
        percent            = %.0f
        ppm                = %.0f
        second             = %.0f
        uv_index           = %.1f
        volt               = %.1f
        watt               = %.1f
        watt_hour          = %.1f
        watt_per_meter_squared = %.0f
        watt_second        = %.0f
        NONE               = "   N/A"

    # The following section sets the label to be used for each type of unit
    [[Labels]]

        amp               = " A"
        bit               = " b"
        boolean           = ""
        byte              = " B"
        centibar          = " cb"
        cm                = " cm"
        cm_per_hour       = " cm/h"
        count             = ""
        cubic_foot        = " ft³"
        day               = " day", " days"
        dB                = " dB"
        degree_C          = "°C"
        degree_C_day      = "°C-day"
        degree_compass    = "°"
        degree_E          = "°E"
        degree_F          = "°F"
        degree_F_day      = "°F-day"
        degree_K          = "°K"
        foot              = " feet"
        gallon            = " gal"
        hour              = " hour", " hours"
        hPa               = " hPa"
        hPa_per_hour      = " hPa/h"
        inch              = " in"
        inch_per_hour     = " in/h"
        inHg              = " inHg"
        inHg_per_hour     = " inHg/h"
        kilowatt_hour     = " kWh"
        km                = " km"
        km_per_hour       = " km/h"
        km_per_hour2      = " km/h"
        knot              = " knots"
        knot2             = " knots"
        kPa               = " kPa",
        kPa_per_hour      = " kPa/h",
        liter             = " l",
        litre             = " l",
        lux               = " lx",
        mbar              = " mbar"
        mbar_per_hour     = " mbar/h"
        mega_joule        = " MJ"
        meter             = " meter", " meters"
        meter_per_second  = " m/s"
        meter_per_second2 = " m/s"
        microgram_per_meter_cubed = " µg/m³",
        mile              = " mile", " miles"
        mile_per_hour     = " mph"
        mile_per_hour2    = " mph"
        minute            = " minute", " minutes"
        mm                = " mm"
        mm_per_hour       = " mm/h"
        mmHg              = " mmHg"
        mmHg_per_hour     = " mmHg/h"
        percent           =   %
        ppm               = " ppm"
        second            = " second", " seconds"
        uv_index          = ""
        volt              = " V"
        watt              = " W"
        watt_hour         = " Wh"
        watt_per_meter_squared = " W/m²"
        watt_second       = " Ws"
        NONE              = ""

    # The following section sets the format to be used for each time scale.
    # The values below will work in every locale, but they may not look
    # particularly attractive. See the Customization Guide for alternatives.
    [[TimeFormats]]

        hour        = %H:%M
        day         = %X
        week        = %X (%A)
        month       = %x %X
        year        = %x %X
        rainyear    = %x %X
        current     = %x %X
        ephem_day   = %X
        ephem_year  = %x %X
        brief_delta = "%(minute)d%(minute_label)s, %(second)d%(second_label)s"
        short_delta = "%(hour)d%(hour_label)s, %(minute)d%(minute_label)s, %(second)d%(second_label)s"
        long_delta  = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s"
        delta_time  = "%(day)d%(day_label)s, %(hour)d%(hour_label)s, %(minute)d%(minute_label)s"

    [[Ordinates]]

        # Ordinal directions. The last one should be for no wind direction
        directions = N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW, N/A

    # The following section sets the base temperatures used for the
    #  calculation of heating and cooling degree-days.
    [[DegreeDays]]

        # Base temperature for heating days, with unit:
        heating_base = 65, degree_F
        # Base temperature for cooling days, with unit:
        cooling_base = 65, degree_F
        # Base temperature for growing days, with unit:
        growing_base = 50, degree_F

    # A trend takes a difference across a time period. The following
    # section sets the time period, and how big an error is allowed to
    # still be counted as the start or end of a period.
    [[Trend]]

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
        outHumidity    = Outside Humidity
        outTemp        = Outside Temperature
        radiation      = Radiation
        rain           = Rain
        rainRate       = Rain Rate
        UV             = UV Index
        wind           = Wind
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
        lightning_distance     = Lightning Distance
        lightning_strike_count = Lightning Strikes

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
