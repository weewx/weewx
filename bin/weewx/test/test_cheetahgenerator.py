# $Id: test_forecast.py 1398 2013-09-24 03:15:37Z mwall $
# Copyright: 2013 Matthew Wall
# License: GPLv3

"""tests for the cheetahgenerator module"""

import configobj
import math
import os
import shutil
import string
import sys
import time
import unittest

import user
import weedb
import weewx
from weewx.filegenerator import FileGenerator
from cheetahgenerator import CheetahGenerator
import user.forecast

def rmdir(d):
    try:
        os.rmdir(d)
    except:
        pass

def rmtree(d):
    try:
        shutil.rmtree(d)
    except:
        pass

def mkdir(d):
    try:
        os.makedirs(d)
    except:
        pass

def rmfile(name):
    try:
        os.remove(name)
    except:
        pass

# FIXME: these belong in a common testing library
TMPDIR = '/var/tmp/weewx_test'

def get_tmpdir():
    return TMPDIR + '/test_cheetahgenerator'

def get_testdir(name):
    return get_tmpdir() + '/' + name

def get_dbdir():
    return get_tmpdir()

PFM_BOS_SINGLE = '''MAZ014-112100-
CAMBRIDGE-MIDDLESEX MA
42.37N  71.12W ELEV. 10 FT
119 PM EDT SAT MAY 11 2013

DATE             SAT 05/11/13            SUN 05/12/13            MON 05/13/13
EDT 3HRLY     05 08 11 14 17 20 23 02 05 08 11 14 17 20 23 02 05 08 11 14 17 20
UTC 3HRLY     09 12 15 18 21 00 03 06 09 12 15 18 21 00 03 06 09 12 15 18 21 00

MAX/MIN                      72          57          69          43          61
TEMP                   69 68 66 63 61 59 62 66 68 68 61 52 47 44 48 56 60 59 53
DEWPT                  59 58 60 58 57 56 56 55 49 41 37 33 31 29 29 29 26 28 26
RH                     70 70 81 84 87 90 81 68 51 37 41 48 53 55 47 35 27 30 35
WIND DIR               SW SW SW  S  S  S SW  W  W  W  W  W  W  W  W  W  W SW  W
WIND SPD               17 14 11  9  8  8 10 11 16 18 14 11 10  8 12  9 16 12  9
WIND GUST                                            27          23 20    23
CLOUDS                 OV OV OV OV OV OV OV OV B2 B1 CL FW CL CL CL FW FW SC SC
POP 12HR                    100          90          70           0           5
QPF 12HR                   0.25        0.14        0.05           0           0
SNOW 12HR                 00-00       00-00       00-00
RAIN SHWRS                 L  D  L  C  L  L  C  C  S
TSTMS                      S  C  S  S        S  S
OBVIS                        PF PF PF PF PF


DATE          TUE 05/14/13  WED 05/15/13  THU 05/16/13  FRI 05/17/13
EDT 6HRLY     02 08 14 20   02 08 14 20   02 08 14 20   02 08 14 20
UTC 6HRLY     06 12 18 00   06 12 18 00   06 12 18 00   06 12 18 00

MIN/MAX          41    60      42    67      49    68      54    70
TEMP          44 47 59 53   45 49 65 60   52 55 67 63   56 59 69 63
DEWPT         35 33 29 32   33 35 34 39   44 48 50 51   52 52 50 50
PWIND DIR        NW    NW      NW    SW       S     S       S    SW
WIND CHAR        GN    LT      LT    LT      LT    LT      LT    LT
AVG CLOUDS    FW FW SC SC   FW FW FW SC   SC B1 B2 B2   B2 B2 B2 B2
POP 12HR          5    10       5    10      20    40      50    40
RAIN SHWRS           S  S                  S  S  S  C    C  C  C  C

$$
'''

class FakeData(object):
    '''generate fake data for testing. portions copied from gen_fake_data.py'''

    start_tt = (2010,1,1,0,0,0,0,0,-1)
    stop_tt  = (2010,3,6,0,0,0,0,0,-1) # 2+ months of data
#    stop_tt  = (2010,1,2,0,0,0,0,0,-1) # one day of data
    start_ts = int(time.mktime(start_tt))
    stop_ts  = int(time.mktime(stop_tt))
    interval = 600

    @staticmethod
    def gen_fake_data(start_ts=start_ts, stop_ts=stop_ts, interval=interval):
        daily_temp_range = 40.0
        annual_temp_range = 80.0
        avg_temp = 40.0

        # Four day weather cycle:
        weather_cycle = 3600*24.0*4
        weather_baro_range = 2.0
        weather_wind_range = 10.0
        avg_baro = 30.0

        count = 0
        for ts in xrange(start_ts, stop_ts+interval, interval):
            daily_phase  = (ts - start_ts) * 2.0 * math.pi / (3600*24.0)
            annual_phase = (ts - start_ts) * 2.0 * math.pi / (3600*24.0*365.0)
            weather_phase= (ts - start_ts) * 2.0 * math.pi / weather_cycle
            record = {}
            record['dateTime']  = ts
            record['usUnits']   = weewx.US
            record['interval']  = interval
            record['outTemp']   = 0.5 * (-daily_temp_range*math.sin(daily_phase) - annual_temp_range*math.cos(annual_phase)) + avg_temp
            record['barometer'] = 0.5 * weather_baro_range*math.sin(weather_phase) + avg_baro
            record['windSpeed'] = abs(weather_wind_range*(1.0 + math.sin(weather_phase)))
            record['windDir'] = math.degrees(weather_phase) % 360.0
            record['windGust'] = 1.2*record['windSpeed']
            record['windGustDir'] = record['windDir']
            if math.sin(weather_phase) > .95:
                record['rain'] = 0.02 if math.sin(weather_phase) > 0.98 else 0.01
            else:
                record['rain'] = 0.0

        # Make every 71st observation (a prime number) a null. This is a
        # deterministic algorithm, so it will produce the same results every
        # time.                             
            for obs_type in filter(lambda x : x not in ['dateTime', 'usUnits', 'interval'], record):
                count+=1
                if count%71 == 0:
                    record[obs_type] = None
            yield record

    @staticmethod
    def create_weather_databases(archive_db_dict, stats_db_dict):
        if os.path.exists(stats_db_dict['database']):
            return
        with weewx.archive.Archive.open_with_create(archive_db_dict, user.schemas.defaultArchiveSchema) as archive:
            archive.addRecord(FakeData.gen_fake_data())
            try:
                weedb.drop(stats_db_dict)
            except weedb.NoDatabase:
                pass
            with weewx.stats.StatsDb.open_with_create(stats_db_dict, user.schemas.defaultStatsSchema) as stats:
                stats.backfillFrom(archive)

    @staticmethod
    def create_forecast_database(forecast_db_dict, records):
        from user.forecast import defaultForecastSchema
        with weewx.archive.Archive.open_with_create(forecast_db_dict, defaultForecastSchema) as archive:
            archive.addRecord(records)


# FIXME: make weewx work without having to specify so many items in config
# for example, these should have sane defaults:
#   Units
#   Labels
#   TimeFormats
class TestConfig(object):
    '''configuration files and objects for testing'''

    metric_unit_groups = '''
        group_altitude     = meter
        group_degree_day   = degree_C_day
        group_direction    = degree_compass
        group_moisture     = centibar
        group_percent      = percent
        group_pressure     = inHg
        group_radiation    = watt_per_meter_squared
        group_rain         = mm
        group_rainrate     = mm_per_hour
        group_speed        = km_per_hour
        group_speed2       = km_per_hour2
        group_temperature  = degree_C
        group_uv           = uv_index
        group_volt         = volt
'''

    us_unit_groups = '''
        group_altitude     = foot
        group_degree_day   = degree_F_day
        group_direction    = degree_compass
        group_moisture     = centibar
        group_percent      = percent
        group_pressure     = mbar
        group_radiation    = watt_per_meter_squared
        group_rain         = inch
        group_rainrate     = inch_per_hour
        group_speed        = mile_per_hour
        group_speed2       = knot2
        group_temperature  = degree_F
        group_uv           = uv_index
        group_volt         = volt
'''

    skin_contents = '''
[Units]
    [[Groups]]
        GROUPS

        # The following groups are used internally and should not be changed:
        group_count        = count
        group_interval     = minute
        group_time         = unix_epoch
        group_elapsed      = second

    [[StringFormats]]
        centibar           = %.0f
        cm                 = %.2f
        cm_per_hour        = %.2f
        degree_C           = %.1f
        degree_F           = %.1f
        degree_compass     = %.0f
        foot               = %.0f
        hPa                = %.1f
        inHg               = %.3f
        inch               = %.2f
        inch_per_hour      = %.2f
        km_per_hour        = %.0f
        km_per_hour2       = %.1f
        knot               = %.0f
        knot2              = %.1f
        mbar               = %.1f
        meter              = %.0f
        meter_per_second   = %.1f
        meter_per_second2  = %.1f
        mile_per_hour      = %.1f
        mile_per_hour2     = %.1f
        mm                 = %.1f
        mmHg               = %.1f
        mm_per_hour        = %.1f
        percent            = %.0f
        uv_index           = %.1f
        volt               = %.1f
        watt_per_meter_squared = %.0f
        NONE               = "    -"

    [[Labels]]
        centibar          = " cb"
        cm                = " cm"
        cm_per_hour       = " cm/hr"
        degree_C          =   C
        degree_F          =   F
        degree_compass    =   deg
        foot              = " feet"
        hPa               = " hPa"
        inHg              = " inHg"
        inch              = " in"
        inch_per_hour     = " in/hr"
        km_per_hour       = " kph"
        km_per_hour2      = " kph"
        knot              = " knots"
        knot2             = " knots"
        mbar              = " mbar"
        meter             = " meters"
        meter_per_second  = " m/s"
        meter_per_second2 = " m/s"
        mile_per_hour     = " mph"
        mile_per_hour2    = " mph"
        mm                = " mm"
        mmHg              = " mmHg"
        mm_per_hour       = " mm/hr"
        percent           =   %
        volt              = " V"
        watt_per_meter_squared = " W/m^2"
        NONE              = ""
        
    [[TimeFormats]]
        day        = %H:%M
        week       = %H:%M on %A
        month      = %d.%m.%Y %H:%M
        year       = %d.%m.%Y %H:%M
        rainyear   = %d.%m.%Y %H:%M
        current    = %d.%m.%Y %H:%M
        ephem_day  = %H:%M
        ephem_year = %d.%m.%Y %H:%M
    [[DegreeDays]]
[Labels]
[Almanac]
    moon_phases = n,wc,fq,wg,f,wg,lq,wc
[FileGenerator]
    encoding = html_entities
    [[SummaryByMonth]]
        [[[NOAA_month]]]
            template = YYYY-MM.txt.tmpl
    [[SummaryByYear]]
        [[[NOAA_year]]]
            template = YYYY.txt.tmpl
    [[ToDate]]
        [[[current]]]
            template = index.html.tmpl
[Generators]
        generator_list = user.filegenerator.FileGenerator
'''

    index_template = '''
<p>
  Monthly summary:&nbsp;
  <select NAME=noaaselect onchange="openNoaaFile(value)">
#for $monthYear in $SummaryByMonth
    <option value="$monthYear">$monthYear</option>
#end for
    <option selected>-Select month-</option>
  </select>
  <br/>
  Yearly summary:&nbsp;
  <select NAME=noaaselect onchange="openNoaaFile(value)">
#for $yr in $SummaryByYear
    <option value="$yr">$yr</option>
#end for
    <option selected>-Select year-</option>
  </select>
</p>
'''

    month_template = '''
#set $D=" %d"
#set $Temp="%6.1f"
#set $NONE="   N/A"
summary for month $month_name $year_name
NAME: $station.location
ELEV: $station.altitude
#for $day in $month.days
#if $day.barometer.count.raw
$day.dateTime.format($D) $day.outTemp.avg.nolabel($Temp,$NONE) $day.outTemp.max.nolabel($Temp,$NONE)
#else
$day.dateTime.format($D)
#end if
#end for

$month.outTemp.avg.nolabel($Temp,$NONE) $month.outTemp.max.nolabel($Temp,$NONE)
'''

    year_template = '''
#set $YM="%Y %m"
#set $Temp="%6.1f"
#set $NONE="   N/A"
summary for year $year_name
NAME: $station.location
ELEV: $station.altitude
#for $month in $year.months
#if $month.barometer.count.raw
$month.dateTime.format($YM) $month.outTemp.meanmax.nolabel($Temp,$NONE) $month.outTemp.meanmin.nolabel($Temp,$NONE)
#else
$month.dateTime.format($YM)
#end if
#end for

$year.outTemp.meanmax.nolabel($Temp,$NONE) $year.outTemp.meanmin.nolabel($Temp,$NONE)
'''

    forecast_template = '''
#set $periods = $forecast.weather_periods('NWS', from_ts=1368328140)
#for $period in $periods
#set $alm = $forecast.almanac(ts=$period.event_ts.raw)
$period.event_ts $period.clouds $alm.sunset
#end for
'''

    @staticmethod
    def create_skin_conf(test_dir, skin_dir='testskin', units=weewx.US,
                         contents=None):
        '''create minimal skin config file for testing'''
        if contents is None:
            contents = TestConfig.skin_contents
        if units == weewx.METRIC:
            groups = TestConfig.metric_unit_groups
        else:
            groups = TestConfig.us_unit_groups
        contents = contents.replace('GROUPS', groups)
        mkdir(test_dir + '/' + skin_dir)
        fn = test_dir + '/' + skin_dir + '/skin.conf'
        f = open(fn, 'w')
        f.write(contents)
        f.close()
        cfg = configobj.ConfigObj(fn)
        return cfg

    @staticmethod
    def create_template(test_dir, skin_dir='testskin',
                        contents='hello world',
                        filename='index.html.tmpl'):
        fn = '%s/%s/%s' % (test_dir, skin_dir, filename)
        f = open(fn, 'w')
        f.write(contents)
        f.close()

    @staticmethod
    def create_config(test_dir, skin_dir='testskin', db_dir=None):
        if db_dir is None:
            db_dir = get_dbdir()
        cd = configobj.ConfigObj()
        cd['debug'] = 1
        cd['WEEWX_ROOT'] = test_dir
        cd['Station'] = {
            'station_type' : 'Simulator',
            'altitude' : [10,'foot'],
            'latitude' : 10,
            'longitude' : 10
            }
        cd['Simulator'] = {
            'driver' : 'weewx.drivers.simulator',
            'mode' : 'generator'
            }
        cd['Engines'] = {
            'WxEngine' : {
                'service_list' : 'weewx.wxengine.StdReport'
                }
            }
        cd['Databases'] = {
            'archive_sqlite' : {
                'root' : '%(WEEWX_ROOT)s',
                'database' : db_dir + '/archive.sdb',
                'driver' : 'weedb.sqlite'
                },
            'stats_sqlite' : {
                'root' : '%(WEEWX_ROOT)s',
                'database' : db_dir + '/stats.sdb',
                'driver' : 'weedb.sqlite'
                }
            }
        cd['StdReport'] = {
            'HTML_ROOT' : test_dir + '/html',
            'SKIN_ROOT' : test_dir,
            'TestReport' : { 'skin' : skin_dir }
            }
        cd['StdArchive'] = {
            'archive_database' : 'archive_sqlite',
            'stats_database' : 'stats_sqlite'
            }
        return cd

content_index_html = '''
<p>
  Monthly summary:&nbsp;
  <select NAME=noaaselect onchange="openNoaaFile(value)">
    <option value="2010-01">2010-01</option>
    <option value="2010-02">2010-02</option>
    <option value="2010-03">2010-03</option>
    <option selected>-Select month-</option>
  </select>
  <br/>
  Yearly summary:&nbsp;
  <select NAME=noaaselect onchange="openNoaaFile(value)">
    <option value="2010">2010</option>
    <option selected>-Select year-</option>
  </select>
</p>
'''

content_2010_txt = '''
summary for year 2010
NAME: Unknown
ELEV: 10 feet
2010 01   21.9  -18.2
2010 02   31.8   -8.4
2010 03   40.6    0.3
2010 04
2010 05
2010 06
2010 07
2010 08
2010 09
2010 10
2010 11
2010 12

  27.7  -12.5
'''

content_2010_01_txt = '''
summary for month Jan 2010
NAME: Unknown
ELEV: 10 feet
 01    0.0   20.0
 02    0.0   20.0
 03    0.0   20.0
 04    0.1   20.1
 05    0.1   20.1
 06    0.2   20.2
 07    0.3   20.3
 08    0.3   20.4
 09    0.4   20.5
 10    0.5   20.6
 11    0.7   20.7
 12    0.8   20.8
 13    0.9   21.0
 14    1.1   21.1
 15    1.2   21.3
 16    1.4   21.5
 17    1.6   21.7
 18    1.8   21.9
 19    2.0   22.1
 20    2.2   22.3
 21    2.5   22.5
 22    2.7   22.8
 23    3.0   23.0
 24    3.2   23.3
 25    3.5   23.6
 26    3.8   23.9
 27    4.1   24.2
 28    4.4   24.5
 29    4.7   24.8
 30    5.0   25.1
 31    5.4   25.5

   1.9   25.5
'''

content_forecast_html = '''
12-May-2013 02:00 OV 13:33
12-May-2013 05:00 OV 13:33
12-May-2013 08:00 OV 13:33
12-May-2013 11:00 OV 13:33
12-May-2013 14:00 B2 13:33
12-May-2013 17:00 B1 13:33
12-May-2013 20:00 CL 13:33
12-May-2013 23:00 FW 13:33
13-May-2013 02:00 CL 13:33
13-May-2013 05:00 CL 13:33
13-May-2013 08:00 CL 13:33
13-May-2013 11:00 FW 13:33
13-May-2013 14:00 FW 13:33
13-May-2013 17:00 SC 13:33
13-May-2013 20:00 SC 13:33
14-May-2013 02:00 FW 13:33
14-May-2013 08:00 FW 13:33
14-May-2013 14:00 SC 13:33
14-May-2013 20:00 SC 13:33
15-May-2013 02:00 FW 13:34
15-May-2013 08:00 FW 13:34
15-May-2013 14:00 FW 13:34
15-May-2013 20:00 SC 13:34
16-May-2013 02:00 SC 13:34
16-May-2013 08:00 B1 13:34
16-May-2013 14:00 B2 13:34
16-May-2013 20:00 B2 13:34
17-May-2013 02:00 B2 13:34
17-May-2013 08:00 B2 13:34
17-May-2013 14:00 B2 13:34
17-May-2013 20:00 B2 13:34
'''


class CheetahGeneratorTest(unittest.TestCase):

    def compare_contents(self, filename, expected):
        expected_lines = string.split(expected, '\n')
        actual = open(filename)
        actual_lines = []
        for actual_line in actual:
            actual_lines.append(actual_line)
        actual.close()
        if len(actual_lines) != len(expected_lines):
            raise AssertionError('wrong number of lines in %s: %d != %d' %
                                 (filename, len(actual_lines),
                                  len(expected_lines)))

        lineno = 0
        diffs = []
        for actual_line in actual_lines:
            try:
                self.assertEqual(string.rstrip(actual_line),
                                 expected_lines[lineno])
            except AssertionError, e:
                diffs.append('line %d: %s' % (lineno+1, e))
            lineno += 1
        if len(diffs) > 0:
            raise AssertionError('differences found in %s:\n%s' %
                                 (filename, '\n'.join(diffs)))

    def setup_databases(self, archive_dict=None, stats_dict=None):
        if archive_dict is None:
            archive_dict = {
                'root' : '%(WEEWX_ROOT)s',
                'database' : get_dbdir() + '/archive.sdb',
                'driver' : 'weedb.sqlite'
                }
        if stats_dict is None:
            stats_dict = {
                'root' : '%(WEEWX_ROOT)s',
                'database' : get_dbdir() + '/stats.sdb',
                'driver' : 'weedb.sqlite'
                }
        FakeData.create_weather_databases(archive_dict, stats_dict)

    # FIXME: the generator code is rather convoluted.
    #   run vs start for cached vs not cached
    #   finalize?
    #   report generator stuffs things into skin_dict from cfg_dict
    # FIXME: setting up to test FileGenerator is a pain
    def setup(self, tdir):
        # create the bits we need to run a report
        self.setup_databases()
        cd = TestConfig.create_config(tdir)
        sd = TestConfig.create_skin_conf(tdir)
        TestConfig.create_template(tdir, filename='index.html.tmpl',
                                   contents=TestConfig.index_template)
        TestConfig.create_template(tdir, filename='YYYY-MM.txt.tmpl',
                                   contents=TestConfig.month_template)
        TestConfig.create_template(tdir, filename='YYYY.txt.tmpl',
                                   contents=TestConfig.year_template)
        stn_info = weewx.station.StationInfo(**cd['Station'])
        ts = FakeData.stop_ts
        first_run = True

        # this is done by reportengine.StdReportEngine.run()
        report = 'TestReport'
        sd['archive_database'] = cd['StdArchive']['archive_database']
        sd['stats_database'] = cd['StdArchive']['stats_database']
        for scalar in cd['StdReport'].scalars:
            sd[scalar] = cd['StdReport'][scalar]
        sd.merge(cd['StdReport'][report])
        sd['REPORT_NAME'] = report

        return (cd, sd, ts, first_run, stn_info)

    def test_filegenerator(self):
        '''test for baseline behavior'''
        tdir = get_testdir('test_filegenerator')
        rmtree(tdir)
        (cd, sd, ts, first_run, stn_info) = self.setup(tdir)

        # run the reports
        gen = FileGenerator(cd, sd, ts, first_run, stn_info)
        gen.start()
        gen.finalize()

        # check the output
        outdir = tdir + '/html/'
        self.compare_contents(outdir + 'index.html', content_index_html)
        self.compare_contents(outdir + '2010.txt', content_2010_txt)
        self.compare_contents(outdir + '2010-01.txt', content_2010_01_txt)

    def test_cheetahgenerator(self):
        tdir = get_testdir('test_cheetahgenerator')
        rmtree(tdir)
        (cd, sd, ts, first_run, stn_info) = self.setup(tdir)

        # run the reports
        gen = CheetahGenerator(cd, sd, ts, first_run, stn_info)
        gen.start()
        gen.finalize()

        # check the output
        outdir = tdir + '/html/'
        self.compare_contents(outdir + 'index.html', content_index_html)
        self.compare_contents(outdir + '2010.txt', content_2010_txt)
        self.compare_contents(outdir + '2010-01.txt', content_2010_01_txt)

    def test_search_list_extension(self):
        tdir = get_testdir('test_search_list_extension')
        rmtree(tdir)
        (cd, sd, ts, first_run, stn_info) = self.setup(tdir)

        # instantiate the generator
        gen = CheetahGenerator(cd, sd, ts, first_run, stn_info)

        # add forecasting extension
        sd['FileGenerator']['search_list_extensions'] = 'user.forecast.ForecastVariables'
        # add forecast template to list of files
        sd['FileGenerator']['ToDate']['forecast'] = {}
        sd['FileGenerator']['ToDate']['forecast']['template'] = 'forecast.html.tmpl'
        # add forecasting database settings
        cd['Forecast'] = {}
        cd['Forecast']['database'] = 'forecast_sqlite'
        db_dir = get_dbdir()
        cd['Databases']['forecast_sqlite'] = {}
        cd['Databases']['forecast_sqlite']['root'] = '%(WEEWX_ROOT)s'
        cd['Databases']['forecast_sqlite']['database'] = db_dir+'/forecast.sdb'
        cd['Databases']['forecast_sqlite']['driver'] =  'weedb.sqlite'
        # create the forecast database
        matrix = user.forecast.NWSParseForecast(PFM_BOS_SINGLE, 'MAZ014')
        records = user.forecast.NWSProcessForecast('BOX', 'MAZ014', matrix)
        FakeData.create_forecast_database(cd['Databases']['forecast_sqlite'],
                                          records)
        # create forecast template
        TestConfig.create_template(tdir, filename='forecast.html.tmpl',
                                   contents=TestConfig.forecast_template)

        # run the reports
        gen.start()
        gen.finalize()

        # check the output
        outdir = tdir + '/html/'
        self.compare_contents(outdir + 'index.html', content_index_html)
        self.compare_contents(outdir + '2010.txt', content_2010_txt)
        self.compare_contents(outdir + '2010-01.txt', content_2010_01_txt)
        self.compare_contents(outdir + 'forecast.html', content_forecast_html)


# use this to run individual tests while debugging
def suite(testname):
    tests = [testname]
    return unittest.TestSuite(map(CheetahGeneratorTest, tests))
            
# use '--test test_name' to specify a single test
if __name__ == '__main__':
    # check for a single test, if not then run them all
    testname = None
    if len(sys.argv) == 3 and sys.argv[1] == '--test':
        testname = sys.argv[2]
    if testname is not None:
        unittest.TextTestRunner(verbosity=2).run(suite(testname))
    else:
        unittest.main()
