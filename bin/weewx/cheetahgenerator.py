#
#    Copyright (c) 2009-2016 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Generate files from templates using the Cheetah template engine.

For more information about Cheetah, see http://www.cheetahtemplate.org

Configuration Options

  encoding = (html_entities|utf8|strict_ascii)
  template = filename.tmpl           # must end with .tmpl
  stale_age = s                      # age in seconds
  search_list = a, b, c
  search_list_extensions = d, e, f

The strings YYYY and MM will be replaced if they appear in the filename.

search_list will override the default search_list

search_list_extensions will be appended to search_list

Both search_list and search_list_extensions must be lists of classes.  Each
class in the list must be derived from SearchList.

Generally it is better to extend by using search_list_extensions rather than
search_list, just in case the default search list changes.

Example:

[CheetahGenerator]
    # How to specify search list extensions:
    search_list_extensions = user.forecast.ForecastVariables, user.extstats.ExtStatsVariables
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

from __future__ import with_statement
import os.path
import syslog
import time

import configobj

import Cheetah.Template
import Cheetah.Filters

import weeutil.weeutil
import weewx.almanac
import weewx.reportengine
import weewx.station
import weewx.units
import weewx.tags
from weeutil.weeutil import to_bool, to_int, timestamp_to_string

# The default search list includes standard information sources that should be
# useful in most templates.
default_search_list = [
    "weewx.cheetahgenerator.Almanac",
    "weewx.cheetahgenerator.Station",
    "weewx.cheetahgenerator.Current",
    "weewx.cheetahgenerator.Stats",
    "weewx.cheetahgenerator.UnitInfo",
    "weewx.cheetahgenerator.Extras"]

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

class CheetahGenerator(weewx.reportengine.ReportGenerator):
    """Class for generating files from cheetah templates.
    
    Useful attributes (some inherited from ReportGenerator):

        config_dict:      The weewx configuration dictionary 
        skin_dict:        The dictionary for this skin
        gen_ts:           The generation time
        first_run:        Is this the first time the generator has been run?
        stn_info:         An instance of weewx.station.StationInfo
        record:           A copy of the "current" record. May be None.
        formatter:        An instance of weewx.units.Formatter
        converter:        An instance of weewx.units.Converter
        search_list_objs: A list holding search list extensions
        db_binder:        An instance of weewx.manager.DBBinder from which the
                          data should be extracted
    """

    generator_dict = {'SummaryByDay'  : weeutil.weeutil.genDaySpans,
                      'SummaryByMonth': weeutil.weeutil.genMonthSpans,
                      'SummaryByYear' : weeutil.weeutil.genYearSpans}
    
    format_dict = {'SummaryByDay'  : "%Y-%m-%d",
                   'SummaryByMonth': "%Y-%m",
                   'SummaryByYear' : "%Y"}

    def run(self):
        """Main entry point for file generation using Cheetah Templates."""

        t1 = time.time()

        self.setup()
        
        # Make a copy of the skin dictionary (we will be modifying it):
        gen_dict = configobj.ConfigObj(self.skin_dict.dict())
        
        # Look for options in [CheetahGenerator],
        section_name = "CheetahGenerator"
        # but accept options from [FileGenerator] for backward compatibility.
        if "FileGenerator" in gen_dict and "CheetahGenerator" not in gen_dict:
            section_name = "FileGenerator"
        
        # The default summary time span is 'None'.
        gen_dict[section_name]['summarize_by'] = 'None'

        # determine how much logging is desired
        log_success = to_bool(gen_dict[section_name].get('log_success', True))

        # configure the search list extensions
        self.initExtensions(gen_dict[section_name])

        # Generate any templates in the given dictionary:
        ngen = self.generate(gen_dict[section_name], self.gen_ts)

        self.teardown()

        elapsed_time = time.time() - t1
        if log_success:
            loginf("Generated %d files for report %s in %.2f seconds" %
                   (ngen, self.skin_dict['REPORT_NAME'], elapsed_time))

    def setup(self):
        # This dictionary will hold the formatted dates of all generated files
        self.outputted_dict = {}
        for k in CheetahGenerator.generator_dict:
            self.outputted_dict[k] = []; 

        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)

    def initExtensions(self, gen_dict):
        """Load the search list"""
        self.search_list_objs = []

        search_list = weeutil.weeutil.option_as_list(gen_dict.get('search_list'))
        if search_list is None:
            search_list = list(default_search_list)

        search_list_ext = weeutil.weeutil.option_as_list(gen_dict.get('search_list_extensions'))
        if search_list_ext is not None:
            search_list.extend(search_list_ext)

        # provide feedback about the requested search list objects
        logdbg("using search list %s" % search_list)

        # Now go through search_list (which is a list of strings holding the
        # names of the extensions):
        for c in search_list:
            x = c.strip()
            if x:
                # Get the class
                class_ = weeutil.weeutil._get_object(x)
                # Then instantiate the class, passing self as the sole argument
                self.search_list_objs.append(class_(self))
                
    def teardown(self):
        """Delete any extension objects we created to prevent back references
        from slowing garbage collection"""
        while len(self.search_list_objs):
            del self.search_list_objs[-1]
            
    def generate(self, section, gen_ts):
        """Generate one or more reports for the indicated section.  Each
        section in a period is a report.  A report has one or more templates.

        section: A ConfigObj dictionary, holding the templates to be
        generated.  Any subsections in the dictionary will be recursively
        processed as well.
        
        gen_ts: The report will be current to this time.
        """
        
        ngen = 0
        # Go through each subsection (if any) of this section,
        # generating from any templates they may contain
        for subsection in section.sections:
            # Sections 'SummaryByMonth' and 'SummaryByYear' imply summarize_by
            # certain time spans
            if not section[subsection].has_key('summarize_by'):
                if subsection == 'SummaryByDay':
                    section[subsection]['summarize_by'] = 'SummaryByDay'
                elif subsection == 'SummaryByMonth':
                    section[subsection]['summarize_by'] = 'SummaryByMonth'
                elif subsection == 'SummaryByYear':
                    section[subsection]['summarize_by'] = 'SummaryByYear'
            # Call recursively, to generate any templates in this subsection
            ngen += self.generate(section[subsection], gen_ts)

        # We have finished recursively processing any subsections in this
        # section. Time to do the section itself. If there is no option
        # 'template', then there isn't anything to do. Return.
        if not section.has_key('template'):
            return ngen
        
        # Change directory to the skin subdirectory.  We use absolute paths
        # for cheetah, so the directory change is not necessary for generating
        # files.  However, changing to the skin directory provides a known
        # location so that calls to os.getcwd() in any templates will return
        # a predictable result.
        os.chdir(os.path.join(self.config_dict['WEEWX_ROOT'],
                              self.skin_dict['SKIN_ROOT'],
                              self.skin_dict['skin']))

        report_dict = weeutil.weeutil.accumulateLeaves(section)
        
        (template, dest_dir, encoding, default_binding) = self._prepGen(report_dict)

        # Get start and stop times        
        default_archive = self.db_binder.get_manager(default_binding)
        start_ts = default_archive.firstGoodStamp()
        if not start_ts:
            loginf('Skipping template %s: cannot find start time' % section['template'])
            return ngen

        if gen_ts:
            record = default_archive.getRecord(gen_ts,
                                               max_delta=to_int(report_dict.get('max_delta')))
            if record:
                stop_ts = record['dateTime']
            else:
                loginf('Skipping template %s: generate time %s not in database' % (section['template'], timestamp_to_string(gen_ts)) )
                return ngen
        else:
            stop_ts = default_archive.lastGoodStamp()
        
        # Get an appropriate generator function
        summarize_by = report_dict['summarize_by']
        if summarize_by in CheetahGenerator.generator_dict:
            _spangen = CheetahGenerator.generator_dict[summarize_by]
        else:
            # Just a single timespan to generate. Use a lambda expression.
            _spangen = lambda start_ts, stop_ts : [weeutil.weeutil.TimeSpan(start_ts, stop_ts)]

        # Use the generator function
        for timespan in _spangen(start_ts, stop_ts):
            start_tt = time.localtime(timespan.start)
            stop_tt  = time.localtime(timespan.stop)

            if summarize_by in CheetahGenerator.format_dict:
                # This is a "SummaryBy" type generation. If it hasn't been done already, save the
                # date as a string, to be used inside the document
                date_str = time.strftime(CheetahGenerator.format_dict[summarize_by], start_tt)
                if date_str not in self.outputted_dict[summarize_by]:
                    self.outputted_dict[summarize_by].append(date_str)
                # For these "SummaryBy" generations, the file name comes from the start of the timespan:
                _filename = self._getFileName(template, start_tt)
            else:
                # This is a "ToDate" generation. File name comes 
                # from the stop (i.e., present) time:
                _filename = self._getFileName(template, stop_tt)

            # Get the absolute path for the target of this template
            _fullname = os.path.join(dest_dir, _filename)

            # Skip summary files outside the timespan
            if report_dict['summarize_by'] in CheetahGenerator.generator_dict \
                    and os.path.exists(_fullname) \
                    and not timespan.includesArchiveTime(stop_ts):
                continue

            # skip files that are fresh, but only if staleness is defined
            stale = to_int(report_dict.get('stale_age'))
            if stale is not None:
                t_now = time.time()
                try:
                    last_mod = os.path.getmtime(_fullname)
                    if t_now - last_mod < stale:
                        logdbg("Skip '%s': last_mod=%s age=%s stale=%s" %
                               (_filename, last_mod, t_now - last_mod, stale))
                        continue
                except os.error:
                    pass

            searchList = self._getSearchList(encoding, timespan,
                                             default_binding)
            tmpname = _fullname + '.tmp'
            
            try:
                compiled_template = Cheetah.Template.Template(
                    file=template,
                    searchList=searchList,
                    filter=encoding,
                    filtersLib=weewx.cheetahgenerator)
                with open(tmpname, mode='w') as _file:
                    print >> _file, compiled_template
                os.rename(tmpname, _fullname)
            except Exception, e:
                # We would like to get better feedback when there are cheetah
                # compiler failures, but there seem to be no hooks for this.
                # For example, if we could get make cheetah emit the source
                # on which the compiler is working, one could compare that with
                # the template to figure out exactly where the problem is.
                # In Cheetah.Compile.ModuleCompiler the source is manipulated
                # a bit then handed off to parserClass.  Unfortunately there
                # are no hooks to intercept the source and spit it out.  So
                # the best we can do is indicate the template that was being
                # processed when the failure ocurred.
                logerr("Generate failed with exception '%s'" % type(e))
                logerr("**** Ignoring template %s" % template)
                logerr("**** Reason: %s" % e)
                weeutil.weeutil.log_traceback("****  ")
            else:
                ngen += 1
            finally:
                try:
                    os.unlink(tmpname)
                except OSError:
                    pass

        return ngen

    def _getSearchList(self, encoding, timespan, default_binding):
        """Get the complete search list to be used by Cheetah."""

        # Get the basic search list
        timespan_start_tt = time.localtime(timespan.start)
        searchList = [{'month_name' : time.strftime("%b", timespan_start_tt),
                       'year_name'  : timespan_start_tt[0],
                       'encoding'   : encoding},
                      self.outputted_dict]
        
        # Bind to the default_binding:
        db_lookup = self.db_binder.bind_default(default_binding)
        
        # Then add the V3.X style search list extensions
        for obj in self.search_list_objs:
            searchList += obj.get_extension_list(timespan, db_lookup)

        return searchList

    def _getFileName(self, template, ref_tt):
        """Calculate a destination filename given a template filename.
        Replace 'YYYY' with the year, 'MM' with the month, 'DD' with the day.
        Strip off any trailing .tmpl"""

        _filename = os.path.basename(template).replace('.tmpl', '')

        # If the filename contains YYYY, MM, or DD, then do the replacement
        if 'YYYY' in _filename or 'MM' in _filename or 'DD' in _filename:
            # Get strings representing year, month, and day
            _yr_str  = "%4d"  % ref_tt[0]
            _mo_str  = "%02d" % ref_tt[1]
            _day_str = "%02d"  % ref_tt[2]
            # Replace any instances of 'YYYY' with the year string
            _filename = _filename.replace('YYYY', _yr_str)
            # Do the same thing with the month...
            _filename = _filename.replace('MM', _mo_str)
            # ... and the day
            _filename = _filename.replace('DD', _day_str)

        return _filename

    def _prepGen(self, report_dict):
        """Get the template, destination directory, encoding, and default
        binding."""

        # -------- Template ---------
        # Cheetah will crash if given a template file name in Unicode. So,
        # convert to ascii, ignoring all characters that cannot be converted:
        template = os.path.join(self.config_dict['WEEWX_ROOT'],
                                self.config_dict['StdReport']['SKIN_ROOT'],
                                report_dict['skin'],
                                report_dict['template']).encode('ascii', 'ignore')
        
        # ------ Destination directory --------
        destination_dir = os.path.join(self.config_dict['WEEWX_ROOT'],
                                       report_dict['HTML_ROOT'],
                                       os.path.dirname(report_dict['template']))
        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(destination_dir)
        except OSError:
            pass

        # ------ Encoding ------
        encoding = report_dict.get('encoding', 'html_entities').strip().lower()
        if encoding == 'utf-8':
            encoding = 'utf8'

        # ------ Default binding ---------
        default_binding = report_dict['data_binding']

        return (template, destination_dir, encoding, default_binding)

# =============================================================================
# Classes used to implement the Search list
# =============================================================================

class SearchList(object):
    """Abstract base class used for search list extensions."""

    def __init__(self, generator):
        """Create an instance of SearchList.

        generator: The generator that is using this search list
        """
        self.generator = generator

    def get_extension_list(self, timespan, db_lookup):  # @UnusedVariable
        """For weewx V3.x extensions. Should return a list
        of objects whose attributes or keys define the extension.
        
        timespan:  An instance of weeutil.weeutil.TimeSpan. This will hold the
                   start and stop times of the domain of valid times.

        db_lookup: A function with call signature db_lookup(data_binding),
                   which returns a database manager and where data_binding is
                   an optional binding name. If not given, then a default
                   binding will be used.
        """
        return [self]

class Almanac(SearchList):
    """Class that implements the '$almanac' tag."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        celestial_ts = generator.gen_ts

        # For better accuracy, the almanac requires the current temperature
        # and barometric pressure, so retrieve them from the default archive,
        # using celestial_ts as the time

        # The default values of temperature and pressure
        temperature_C = 15.0
        pressure_mbar = 1010.0

        # See if we can get more accurate values by looking them up in the
        # weather database. The database might not exist, so be prepared for
        # a KeyError exception.
        try:
            archive = self.generator.db_binder.get_manager()
        except (KeyError, weewx.UnknownBinding):
            pass
        else:
            # If a specific time has not been specified, then use the timestamp
            # of the last record in the database.
            if not celestial_ts:
                celestial_ts = archive.lastGoodStamp()

            # Check to see whether we have a good time. If so, retrieve the
            # record from the database    
            if celestial_ts:
                # Look for the record closest in time. Up to one hour off is
                # acceptable:
                rec = archive.getRecord(celestial_ts, max_delta=3600)
                if rec is not None:
                    if 'outTemp' in rec:
                        temperature_C = weewx.units.convert(weewx.units.as_value_tuple(rec, 'outTemp'), "degree_C")[0]
                    if 'barometer' in rec:
                        pressure_mbar = weewx.units.convert(weewx.units.as_value_tuple(rec, 'barometer'), "mbar")[0]
        
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
    """Class that implements the $station tag."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)
        self.station = weewx.station.Station(generator.stn_info,
                                             generator.formatter,
                                             generator.converter,
                                             generator.skin_dict)
        
class Current(SearchList):
    """Class that implements the $current tag"""
     
    def get_extension_list(self, timespan, db_lookup):
        record_binder = weewx.tags.RecordBinder(db_lookup, timespan.stop,
                                                self.generator.formatter, self.generator.converter, 
                                                record=self.generator.record)
        return [record_binder]
    
class Stats(SearchList):
    """Class that implements the time-based statistical tags, such
    as $day.outTemp.max"""


    def get_extension_list(self, timespan, db_lookup):
        try:
            trend_dict = self.generator.skin_dict['Units']['Trend']
        except KeyError:
            trend_dict = {'time_delta' : 10800,
                          'time_grace' : 300}

        stats = weewx.tags.TimeBinder(
            db_lookup,
            timespan.stop,
            formatter=self.generator.formatter,
            converter=self.generator.converter,
            week_start=self.generator.stn_info.week_start,
            rain_year_start=self.generator.stn_info.rain_year_start,
            trend=trend_dict,
            skin_dict=self.generator.skin_dict)

        return [stats]

class UnitInfo(SearchList):
    """Class that implements the $unit tag."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)
        # This implements the $unit tag:
        self.unit = weewx.units.UnitInfoHelper(generator.formatter,
                                               generator.converter)
        # This implements the $obs tag:
        self.obs = weewx.units.ObsInfoHelper(generator.skin_dict)

class Extras(SearchList):
    """Class for exposing the [Extras] section in the skin config dictionary
    as tag $Extras."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)
        # If the user has supplied an '[Extras]' section in the skin
        # dictionary, include it in the search list. Otherwise, just include
        # an empty dictionary.
        self.Extras = generator.skin_dict['Extras'] if generator.skin_dict.has_key('Extras') else {}
    
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
