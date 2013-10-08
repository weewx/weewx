#
#    Copyright (c) 2009, 2010, 2013 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Generate files from templates using the Cheetah template engine.

For more information about Cheetah, see http://www.cheetahtemplate.org

search_list = a, b, c
encoding = (html_entities|utf8|strict_ascii)
template = filename.tmpl
stale_age = s

The strings YYYY and MM will be replaced if they appear in the filename.

Example:

[CheetahGenerator]
    search_list = user.forecast.ForecastVariables, user.extstats.ExtStatsVariables, weewx.cheetahgenerator.Almanac, weewx.cheetahgenerator.Station, weewx.cheetahgenerator.Stats, weewx.cheetahgenerator.UnitInfo, weewx.cheetahgenerator.Extras, weewx.cheetahgenerator.Current
    encoding = html_entities      # html_entities, utf8, strict_ascii
    [[SummaryByMonth]]                              # period
        [[[NOAA_month]]]                            # report
            encoding = strict_ascii
            template = NOAA-YYYY-MM.txt.tmpl
    [[SummaryByYear]]
        [[[NOAA_year]]]]
            encoding = strict_ascii
            template = NOAA-YYYY.txt.tmpl
    [[ToDate]]
        [[[day]]]
            template = index.html.tmpl
        [[[week]]]
            template = week.html.tmpl
    [[wuforecast_details]]                 # period/report
        stale_age = 3600                   # how old before regenerating
        template = wuforecast.html.tmpl
    [[nwsforecast_details]]                # period/report
        stale_age = 10800                  # how old before generating
        template = nwsforecast.html.tmpl

"""

import os.path
import sys
import syslog
import time
import urlparse

import Cheetah.Template
import Cheetah.Filters

import weeutil.weeutil
import weewx.almanac
import weewx.reportengine
import weewx.station
import weewx.units

# Default base temperature and unit type for heating and cooling degree days
# as a value tuple
default_heatbase = (65.0, "degree_F", "group_temperature")
default_coolbase = (65.0, "degree_F", "group_temperature")

# Default search list:
default_search_list = ["weewx.cheetahgenerator.Almanac", "weewx.cheetahgenerator.Station", 
                       "weewx.cheetahgenerator.Stats",   "weewx.cheetahgenerator.UnitInfo",
                       "weewx.cheetahgenerator.Extras",  "weewx.cheetahgenerator.Current"]

def logmsg(lvl, msg):
    syslog.syslog(lvl, 'cheetahgenerator: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def logcrt(msg):
    logmsg(syslog.LOG_CRIT, msg)

# =============================================================================
# CheetahGenerator
# =============================================================================

class CheetahGenerator(weewx.reportengine.CachedReportGenerator):
    """Class for generating files from cheetah templates.
    
    Useful attributes (some inherited from ReportGenerator):

        config_dict:      The weewx configuration dictionary 
        skin_dict:        The dictionary for this skin
        gen_dict:         The section ['CheetahGenerator'] from skin.conf
        gen_ts:           The generation time
        first_run:        Whether this is the first time the generator has been run
        stn_info:         An instance of weewx.station.StationInfo
        formatter:        An instance of weewx.units.Formatter
        converter:        An instance of weewx.units.Converter
        unitInfoHelper:   An instance of weewx.units.UnitInfoHelper
        search_list_objs: A list holding the search list objects
    """

    def run(self):
        self.setup()
        for time_period in self.gen_dict.sections:
            self.generate(time_period, self.gen_ts)
        self.teardown()

    def setup(self):
        # Look for my section name, but accept [FileGenerator] for backwards compatibility:
        self.gen_dict = self.skin_dict['CheetahGenerator'] if self.skin_dict.has_key('CheetahGenerator') else self.skin_dict['FileGenerator']
        self.outputted_dict = {'SummaryByMonth' : [], 'SummaryByYear'  : [] }

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

        self.initExtensions()

    def teardown(self):
        self.deleteExtensions()

    def initExtensions(self):
        """Load the search list"""
        self.search_list_objs = []

        search_list = weeutil.weeutil.option_as_list(self.gen_dict.get('search_list'))
        if search_list is None:
            search_list = default_search_list

        for c in search_list:
            x = c.strip()
            if len(x) > 0:
                logdbg("loading search list extension '%s'" % c)
                Cls = weeutil.weeutil._get_object(c)
                self.search_list_objs.append(Cls(self))

    def deleteExtensions(self):
        """delete any extension objects we created to prevent back references
        from blocking garbage collection"""
        while len(self.search_list_objs):
            del self.search_list_objs[-1]

    def generate(self, period, gen_ts):
        """Generate one or more reports for the indicated period.  Each section
        in a period is a report.  A report has one or more templates.

        The periods SummaryByMonth and SummaryByYear get special treatment."""

        logdbg('generating for period %s' % period)

        # break the period into time spans as necessary.
        # SummaryByMonth and SummaryByYear have spans plus special meaning.
        spans = self.gen_dict[period].get('spans', None)
        if spans is None:
            if period == 'SummaryByMonth':
                spans = 'month'
            elif period == 'SummaryByYear':
                spans = 'year'
        if spans == 'month':
            _spangen = weeutil.weeutil.genMonthSpans
        elif spans == 'year':
            _spangen = weeutil.weeutil.genYearSpans
        else:
            _spangen = self.genSingleSpan;

        # a period may have a single template, or it might have sections,
        # each with its own template.
        sections = self.gen_dict[period].sections
        if sections is None:
            reports = [period]
        else:
            reports = sections

        ngen = 0
        t1 = time.time()
        for report in reports:
            if sections is None:
                report_dict = self.gen_dict[period]
            else:
                report_dict = self.gen_dict[period][report]
            (template, statsdb, archivedb, dest_dir, encoding) = self._prepGen(report_dict)
            start_ts = archivedb.firstGoodStamp()
            if not start_ts:
                loginf('skipping report %s: cannot find start time' % period)
                break
            stop_ts = gen_ts if gen_ts else archivedb.lastGoodStamp()

            for timespan in _spangen(start_ts, stop_ts):
                logdbg('period=%s report=%s timespan=%s' %
                       (period, report, timespan))

                # Save YYYY-MM so they can be used within the document
                if period == 'SummaryByMonth' or period == 'SummaryByYear':
                    timespan_start_tt = time.localtime(timespan.start)
                    _yr_str = "%4d" % timespan_start_tt[0]
                    if period == 'SummaryByMonth':
                        _mo_str = "%02d" % timespan_start_tt[1]
                        self.outputted_dict['SummaryByMonth'].append("%s-%s" % (_yr_str, _mo_str))
                    if period == 'SummaryByYear':
                        self.outputted_dict['SummaryByYear'].append(_yr_str)

                # figure out the filename for this template
                _filename = self._getFileName(template, timespan)
                _fullname = os.path.join(dest_dir, _filename)
                logdbg('fullname=%s' % _fullname)

                # skip files that are fresh, only if staleness is defined
                stale = report_dict.get('stale_age', None)
                if stale is not None:
                    stale = int(stale)
                    try:
                        last_mod = os.path.getmtime(_fullname)
                        stale_at = t1 - stale
                        if last_mod > stale_at:
                            logdbg("skip file '%s' last_mod=%s stale_at=%s" %
                                   (_filename, last_mod, stale_at))
                            break
                    except os.error:
                        pass

                searchList = self._getSearchList(encoding, timespan, archivedb, statsdb)
                text = Cheetah.Template.Template(file=template,
                                                 searchList=searchList,
                                                 filter=encoding,
                                                 filtersLib=weewx.cheetahgenerator)
                _file = None
                try:
                    _file = open(_fullname, mode='w')
                    print >> _file, text
                except Exception, e:
                    logerr("generate failed with exception '%s'" % type(e))
                    logerr("**** ignoring template %s" % template)
                    logerr("**** reason: %s" % e)
                    weeutil.weeutil.log_traceback("****  ")
                else:
                    ngen += 1
                finally:
                    if _file is not None: _file.close()
        elapsed_time = time.time() - t1
        loginf("generated %d '%s' files for %s in %.2f seconds" %
               (ngen, period, self.skin_dict['REPORT_NAME'], elapsed_time))

    def _getSearchList(self, encoding, timespan, archivedb, statsdb):
        """Get the complete search list to be used by Cheetah."""

        timespan_start_tt = time.localtime(timespan.start)

        searchList = [{'month_name' : time.strftime("%b", timespan_start_tt),
                       'year_name'  : timespan_start_tt[0],
                       'encoding' : encoding},
                      self.outputted_dict] \
            + [obj.get_extension(timespan, archivedb, statsdb) for obj in self.search_list_objs]\
            + self.getToDateSearchList(archivedb, statsdb, timespan)

        return searchList

    def getToDateSearchList(self, archivedb, statsdb, timespan):
        """Backwards compatible entry."""
        return []

    def _getFileName(self, template, timespan):
        """Calculate a destination filename given a template filename.
        Replace 'YYYY' with the year, 'MM' with the month.  Strip off any
        trailing .tmpl"""

        _filename = os.path.basename(template).replace('.tmpl', '')

        if _filename.find('YYYY') >= 0 or _filename.find('MM') >= 0:
            # Start by getting the start time as a timetuple.
            timespan_start_tt = time.localtime(timespan.start)
            # Get a string representing the year (e.g., '2009') and month
            _yr_str = "%4d"  % timespan_start_tt[0]
            _mo_str = "%02d" % timespan_start_tt[1]
            # Replace any instances of 'YYYY' with the year string
            _filename = _filename.replace('YYYY', _yr_str)
            # Do the same thing with the month
            _filename = _filename.replace('MM', _mo_str)

        return _filename

    def genSingleSpan(self, start_ts, stop_ts):
        """Generator function used when doing "to date" generation."""
        return [weeutil.weeutil.TimeSpan(start_ts, stop_ts)]

    def _getRecord(self, archivedb, time_ts):
        """Get an observation record from the archive database, returning
        it as a ValueDict."""

        # Get the record...
        record_dict = archivedb.getRecord(time_ts)
        if record_dict is None: return None
        # ... convert to a dictionary with ValueTuples as values...
        record_dict_vt = weewx.units.dictFromStd(record_dict)
        # ... then wrap it in a ValueDict:
        record_vd = weewx.units.ValueDict(record_dict_vt, context='current',
                                          formatter=self.formatter,
                                          converter=self.converter)
        return record_vd

    def _prepGen(self, subskin_dict):
        """Gather the options together for a specific report, then
        retrieve the template file, stats database, archive database,
        the destination directory, and the encoding from those options."""

        # Walk the tree back to the root, accumulating options
        accum_dict = weeutil.weeutil.accumulateLeaves(subskin_dict)
        template = os.path.join(self.config_dict['WEEWX_ROOT'],
                                self.config_dict['StdReport']['SKIN_ROOT'],
                                accum_dict['skin'],
                                accum_dict['template'])
        destination_dir = os.path.join(self.config_dict['WEEWX_ROOT'],
                                       accum_dict['HTML_ROOT'],
                                       os.path.dirname(accum_dict['template']))
        encoding = accum_dict['encoding']

        statsdb   = self._getStats(accum_dict['stats_database'])
        archivedb = self._getArchive(accum_dict['archive_database'])

        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(destination_dir)
        except OSError:
            pass

        return (template, statsdb, archivedb, destination_dir, encoding)

class TrendObj(object):
    """Helper class that binds together a current record and one a delta
    time in the past. Useful for trends.
    
    This class allows tags such as:
      $trend.barometer
    """
        
    def __init__(self, last_rec, now_rec, time_delta):
        """Initialize a Trend object
        
        last_rec: A ValueDict containing records from the past.
        
        now_rec: A ValueDict containing current records
        
        time_delta: The time difference in seconds between them.
        """
        self.last_rec = last_rec
        self.now_rec  = now_rec
        self.time_delta = weewx.units.ValueHelper((time_delta, 'second', 'group_elapsed'))
        
    def __getattr__(self, obs_type):
        """Return the trend for the given observation type."""
        # The following is so the Python version of Cheetah's NameMapper
        # does not think I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError
        
        # Wrap in a try block because the 'last' record might not exist,
        # or the 'now' or 'last' value might be None. 
        try:
            # Do the unit conversion now, rather than lazily. This is because,
            # in the case of temperature, the difference between two converted
            # values is not the same as the conversion of the difference
            # between two values. E.g., 20C - 10C is not equal to
            # F_to_C(68F - 50F). We want the former, not the latter.  
            vt_now = self.now_rec[obs_type]._raw_value_tuple
            trend = vt_now - self.last_rec[obs_type]._raw_value_tuple
        except TypeError:
            trend = (None,) + vt_now[1:3]

        # Return the results as a ValueHelper. Use the formatting and labeling
        # options from the current time record. The user can always override
        # these.
        return weewx.units.ValueHelper(trend, self.now_rec.context,
                                       self.now_rec.formatter,
                                       self.now_rec.converter)

# =============================================================================
# Classes used to implement the Search list
# =============================================================================

class SearchList(object):
    """Provide binding between variable name and data"""

    def __init__(self, generator):
        """Create an instance of the search list.

        generator: The generator that is using this search list
        """
        self.generator = generator

    def get_extension(self, timespan, archivedb, statsdb):
        """Derived classes must define this method.  Should return an object
        whose attributes or keys define the extension.
        
        timespan:  An instance of weeutil.weeutil.TimeSpan. This will hold the
                   start and stop times of the domain of valid times.
                   
        archivedb: An instance of class weewx.archive.Archive.
        
        statsdb:   An instance of class weewx.stats.StatsDb
        """
        return self

class Almanac(SearchList):
    """Class that implements the '$almanac' tag."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        celestial_ts = generator.gen_ts

        # For better accuracy, the almanac requires the current temperature
        # and barometric pressure, so retrieve them from the default archive,
        # using celestial_ts as the time

        temperature_C = pressure_mbar = None

        archivedb = generator._getArchive(generator.skin_dict['archive_database'])
        if not celestial_ts:
            celestial_ts = archivedb.lastGoodStamp()
        rec = generator._getRecord(archivedb, celestial_ts)

        if rec is not None:
            if rec.has_key('outTemp'):
                temperature_C = rec['outTemp'].degree_C.raw
            if rec.has_key('barometer'):
                pressure_mbar = rec['barometer'].mbar.raw
        if temperature_C is None: temperature_C = 15.0
        if pressure_mbar is None: pressure_mbar = 1010.0

        self.moonphases = generator.skin_dict.get('Almanac', {}).get('moon_phases', weeutil.Moon.moon_phases)

        altitude_vt = weewx.units.convert(generator.stn_info.altitude_vt, "meter")

        self.almanac = weewx.almanac.Almanac(celestial_ts,
                                             generator.stn_info.latitude_f,
                                             generator.stn_info.longitude_f,
                                             altitude=altitude_vt[0],
                                             temperature=temperature_C,
                                             pressure=pressure_mbar,
                                             moon_phases=self.moonphases,
                                             formatter=generator.formatter)

class Station(SearchList):
    """Class that implements the '$station' tag."""
    def __init__(self, generator):
        SearchList.__init__(self, generator)
        self.station = weewx.station.Station(generator.stn_info,
                                             generator.formatter, generator.converter,
                                             generator.skin_dict)
        
class Stats(SearchList):
    """Class that implements the time-based statistical tags, such as $day.outTemp.max"""

    def get_extension(self, timespan, archivedb, statsdb):
        heatbase = self.generator.skin_dict['Units']['DegreeDays'].get('heating_base')
        coolbase = self.generator.skin_dict['Units']['DegreeDays'].get('heating_base')
        heatbase_t = (float(heatbase[0]), heatbase[1], "group_temperature") if heatbase else default_heatbase
        coolbase_t = (float(coolbase[0]), coolbase[1], "group_temperature") if coolbase else default_coolbase

        # Get a TaggedStats structure. This allows constructs such as
        # stats.month.outTemp.max
        stats = weewx.stats.TaggedStats(statsdb,
                                        timespan.stop,
                                        formatter=self.generator.formatter,
                                        converter=self.generator.converter,
                                        rain_year_start=self.generator.stn_info.rain_year_start,
                                        heatbase=heatbase_t,
                                        coolbase=coolbase_t,
                                        week_start=self.generator.stn_info.week_start)

        return stats

class UnitInfo(SearchList):
    """Class that implements the '$unit' tag."""
    def __init__(self, generator):
        SearchList.__init__(self, generator)
        self.unit = weewx.units.UnitInfoHelper(generator.formatter,
                                               generator.converter)

class Extras(SearchList):
    """Class for exposing the [Extras] section in the skin config dictionary as tag $Extras."""
    def __init__(self, generator):
        SearchList.__init__(self, generator)
        # If the user has supplied an '[Extras]' section in the skin
        # dictionary, include it in the search list. Otherwise, just include
        # an empty dictionary.
        self.Extras = generator.skin_dict['Extras'] if generator.skin_dict.has_key('Extras') else {}

class Current(SearchList):
    """Class for implementing the $current and $trend tags"""

    def get_extension(self, timespan, archivedb, statsdb):

        try:
            time_delta = int(self.generator.skin_dict['Units']['Trend']['time_delta'])
        except KeyError:
            time_delta = 10800  # 3 hours

        # Get current record, and one from the beginning of the trend period.
        current_rec = self.generator._getRecord(archivedb, timespan.stop)
        former_rec = self.generator._getRecord(archivedb, timespan.stop - time_delta)

        return {'current' : current_rec,
                'trend'   : TrendObj(former_rec, current_rec, time_delta)}
        
# =============================================================================
# Filters used for encoding
# =============================================================================

class html_entities(Cheetah.Filters.Filter):

    def filter(self, val, **dummy_kw): #@ReservedAssignment
        """Filter incoming strings so they use HTML entity characters"""
        if isinstance(val, unicode):
            filtered = val.encode('ascii', 'xmlcharrefreplace')
        elif val is None:
            filtered = ''
        elif isinstance(val, str):
            filtered = val.decode('utf-8').encode('ascii', 'xmlcharrefreplace')
        else:
            filtered = self.filter(str(val))
        return filtered

class strict_ascii(Cheetah.Filters.Filter):

    def filter(self, val, **dummy_kw): #@ReservedAssignment
        """Filter incoming strings to strip out any non-ascii characters"""
        if isinstance(val, unicode):
            filtered = val.encode('ascii', 'ignore')
        elif val is None:
            filtered = ''
        elif isinstance(val, str):
            filtered = val.decode('utf-8').encode('ascii', 'ignore')
        else:
            filtered = self.filter(str(val))
        return filtered
    
class utf8(Cheetah.Filters.Filter):

    def filter(self, val, **dummy_kw): #@ReservedAssignment
        """Filter incoming strings, converting to UTF-8"""
        if isinstance(val, unicode):
            filtered = val.encode('utf8')
        elif val is None:
            filtered = ''
        else:
            filtered = str(val)
        return filtered
