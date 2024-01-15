#
#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate fake data used by the tests.

The idea is to create a deterministic database that reports
can be run against, resulting in predictable, expected results"""

import logging
import math
import os
import time

import weecfg.database
import weedb
import weewx.manager

log = logging.getLogger(__name__)

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# The start of the 'solar year' for 2009-2010
year_start_tt = (2009, 12, 21, 9, 47, 0, 0, 0, 0)
year_start = int(time.mktime(year_start_tt))

# Roughly nine months of data:
start_tt = (2010, 1, 1, 0, 0, 0, 0, 0, -1)  # 2010-01-01 00:00
stop_tt = (2010, 9, 3, 11, 0, 0, 0, 0, -1)  # 2010-09-03 11:00
alt_start_tt = (2010, 8, 30, 0, 0, 0, 0, 0, -1)
start_ts = int(time.mktime(start_tt))
stop_ts = int(time.mktime(stop_tt))
alt_start = int(time.mktime(alt_start_tt))

# At one half-hour archive intervals:
interval = 1800

altitude_vt = (700, 'foot', 'group_altitude')
latitude = 45
longitude = -125

daily_temp_range = 40.0
annual_temp_range = 80.0
avg_temp = 40.0

# Four day weather cycle:
weather_cycle = 3600 * 24.0 * 4
weather_baro_range = 2.0
weather_wind_range = 10.0
weather_rain_total = 0.5  # This is inches per weather cycle
avg_baro = 30.0


def make_nulls_filter(record):
    """Values of inTemp for the first half of the database will have nulls,
    the second half will not."""
    if record['dateTime'] > (start_ts + stop_ts)/2:
        record['inTemp'] = 68.0
    return record


def configDatabases(config_dict, database_type, record_filter=make_nulls_filter):
    config_dict['DataBindings']['wx_binding']['database'] = "archive_" + database_type
    configDatabase(config_dict, 'wx_binding', record_filter=record_filter)
    config_dict['DataBindings']['alt_binding']['database'] = "alt_" + database_type
    configDatabase(config_dict, 'alt_binding', start_ts=alt_start, amplitude=0.5, record_filter=record_filter)


def configDatabase(config_dict, binding, start_ts=start_ts, stop_ts=stop_ts, interval=interval, amplitude=1.0,
                   day_phase_offset=math.pi / 4.0, annual_phase_offset=0.0,
                   weather_phase_offset=0.0, year_start=start_ts, record_filter=lambda r: r):
    """Configures the archive databases."""

    # Check to see if it already exists and is configured correctly.
    try:
        with weewx.manager.open_manager_with_config(config_dict, binding)  as manager:
            if manager.firstGoodStamp() == start_ts and manager.lastGoodStamp() == stop_ts:
                # Before weewx V4, the test database had interval in seconds.
                # Check that this one has been corrected.
                last_record = manager.getRecord(stop_ts)
                if last_record['interval'] == interval / 60:
                    # Database exists, and it has the right value for interval. We're done.
                    return
                else:
                    log.info("Interval value is wrong. Rebuilding test databases.")

    except weedb.DatabaseError:
        pass

    # Delete anything that might already be there.
    try:
        log.info("Dropping database %s" % config_dict['DataBindings'][binding]['database'])
        weewx.manager.drop_database_with_config(config_dict, binding)
    except weedb.DatabaseError:
        pass

    # Need to build a new synthetic database. General strategy is to create the
    # archive data, THEN backfill with the daily summaries. This is faster than
    # creating the daily summaries on the fly. 
    # First, we need to modify the configuration dictionary that was passed in
    # so it uses the DBManager, instead of the daily summary manager
    monkey_dict = config_dict.dict()
    monkey_dict['DataBindings'][binding]['manager'] = 'weewx.manager.Manager'

    with weewx.manager.open_manager_with_config(monkey_dict, binding, initialize=True) as archive:

        log.info("Creating synthetic database %s" % config_dict['DataBindings'][binding]['database'])

        # Because this can generate voluminous log information,
        # suppress all but the essentials:
        logging.disable(logging.INFO)

        # Now generate and add the fake records to populate the database:
        t1 = time.time()
        archive.addRecord(
            filter(record_filter,
                   genFakeRecords(start_ts=start_ts, stop_ts=stop_ts,
                                  interval=interval,
                                  amplitude=amplitude,
                                  day_phase_offset=day_phase_offset,
                                  annual_phase_offset=annual_phase_offset,
                                  weather_phase_offset=weather_phase_offset,
                                  year_start=start_ts,
                                  db_manager=archive)
                   )
                          )
        t2 = time.time()
        delta = t2 - t1
        print("\nTime to create synthetic database '%s' = %6.2fs"
              % (config_dict['DataBindings'][binding]['database'], delta))

        # Restore the logging
        logging.disable(logging.NOTSET)

    with weewx.manager.open_manager_with_config(config_dict, binding, initialize=True) as archive:

        # Backfill with daily summaries:
        t1 = time.time()
        nrecs, ndays = archive.backfill_day_summary()
        tdiff = time.time() - t1
        if nrecs:
            print("\nProcessed %d records to backfill %d day summaries in database '%s' in %.2f seconds"
                  % (nrecs, ndays, config_dict['DataBindings'][binding]['database'], tdiff))
        else:
            print("Daily summaries in database '%s' up to date."
                  % config_dict['DataBindings'][binding]['database'])

        t1 = time.time()
        patch_database(config_dict, binding)
        tdiff = time.time() - t1
        print("\nTime to patch database with derived types: %.2f seconds" % tdiff)


def genFakeRecords(start_ts=start_ts, stop_ts=stop_ts, interval=interval,
                   amplitude=1.0, day_phase_offset=0.0, annual_phase_offset=0.0,
                   weather_phase_offset=0.0, year_start=start_ts, db_manager=None):
    """Generate records from start_ts to stop_ts, inclusive.
    start_ts: Starting timestamp in unix epoch time. This timestamp will be included in the results.

    stop_ts: Stopping timestamp in unix epoch time. This timestamp will be included in the results.

    interval: The interval between timestamps IN SECONDS!
    """
    count = 0

    for ts in range(start_ts, stop_ts + interval, interval):
        daily_phase = ((ts - year_start) * 2.0 * math.pi) / (3600 * 24.0) + day_phase_offset
        annual_phase = ((ts - year_start) * 2.0 * math.pi) / (3600 * 24.0 * 365.0) + annual_phase_offset
        weather_phase = ((ts - year_start) * 2.0 * math.pi) / weather_cycle + weather_phase_offset
        record = {
            'dateTime': ts,
            'usUnits': weewx.US,
            'interval': int(interval / 60),
            'outTemp': 0.5 * amplitude * (-daily_temp_range * math.sin(daily_phase)
                                          - annual_temp_range * math.cos(annual_phase)) + avg_temp,
            'barometer': -0.5 * amplitude * weather_baro_range * math.sin(weather_phase) + avg_baro,
            'windSpeed': abs(amplitude * weather_wind_range * (1.0 + math.sin(weather_phase))),
            'windDir': math.degrees(weather_phase) % 360.0,
            'outHumidity': 40 * math.sin(weather_phase) + 50,
            'stringData' : "S%d" % ts,
        }
        record['windGust'] = 1.2 * record['windSpeed']
        record['windGustDir'] = record['windDir']
        if math.sin(weather_phase) > .95:
            record['rain'] = 0.08 * amplitude if math.sin(weather_phase) > 0.98 else 0.04 * amplitude
        else:
            record['rain'] = 0.0
        record['radiation'] = max(amplitude * 800 * math.sin(daily_phase - math.pi / 2.0), 0)
        record['radiation'] *= 0.5 * (math.cos(annual_phase + math.pi) + 1.5)
        record['sunshineDur'] = interval if record['radiation'] else 0.0

        # Make every 71st observation (a prime number) a null. This is a deterministic algorithm, so it
        # will produce the same results every time.
        for obs_type in ['barometer', 'outTemp', 'windDir', 'windGust', 'windGustDir', 'windSpeed']:
            count += 1
            if count % 71 == 0:
                record[obs_type] = None

        # Round the values slightly so we don't get small assertion errors from SQL arithmetic.
        for obs_type in ['barometer', 'outTemp', 'windDir', 'windGust', 'windGustDir', 'windSpeed']:
            if record.get(obs_type) is not None:
                record[obs_type] = round(record[obs_type], 6)
        yield record



def patch_database(config_dict, binding='wx_binding'):
    calc_missing_config_dict = {
        'name': 'Patch gen_fake_data',
        'binding': binding,
        'start_ts': start_ts,
        'stop_ts': stop_ts,
        'dry_run': False,
    }
    calc_missing = weecfg.database.CalcMissing(config_dict, calc_missing_config_dict)
    calc_missing.run()


if __name__ == '__main__':
    count = 0
    for rec in genFakeRecords():
        if count % 30 == 0:
            print("Time                        outTemp   windSpeed   barometer rain radiation stringData")
        count += 1
        outTemp = "%10.1f" % rec['outTemp'] if rec['outTemp'] is not None else "       N/A"
        windSpeed = "%10.1f" % rec['windSpeed'] if rec['windSpeed'] is not None else "       N/A"
        barometer = "%10.1f" % rec['barometer'] if rec['barometer'] is not None else "       N/A"
        rain = "%10.2f" % rec['rain'] if rec['rain'] is not None else "       N/A"
        radiation = "%10.0f" % rec['radiation'] if rec['radiation'] is not None else "       N/A"
        string_data = " %s" % rec['stringData']
        print(7 * "%s" % (time.ctime(rec['dateTime']),
                          outTemp,
                          windSpeed,
                          barometer,
                          rain,
                          radiation,
                          string_data))
