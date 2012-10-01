#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Generate files from templates."""

import os.path
import sys
import syslog
import time
import urlparse

import Cheetah.Template
import Cheetah.Filters

import weedb
import weeutil.weeutil
import weewx.almanac
import weewx.reportengine
import weewx.station
import weewx.units

# Default base temperature and unit type for heating and cooling degree days
# as a value tuple
default_heatbase = (65.0, "degree_F", "group_temperature")
default_coolbase = (65.0, "degree_F", "group_temperature")

#===============================================================================
#                    Class FileGenerator
#===============================================================================

class FileGenerator(weewx.reportengine.CachedReportGenerator):
    """Class for managing the template based generators"""
    
    def run(self):

        self.setup()
        self.generateSummaryBy('SummaryByMonth', self.gen_ts)
        self.generateSummaryBy('SummaryByYear', self.gen_ts)
        self.generateToDate(self.gen_ts)

    def setup(self):
        
        self.outputted_dict = {'SummaryByMonth' : [],
                               'SummaryByYear'  : []}
        self.initUnits()
        self.initStation()
        self.initAlmanac(self.gen_ts)
        
    def initUnits(self):
        
        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)
        self.unitInfoHelper = weewx.units.UnitInfoHelper(self.formatter, self.converter)
        
    def initStation(self):

        try:
            website = "http://" + self.config_dict['StdReport']['FTP']['server']
            webpath = urlparse.urljoin(website, self.config_dict['StdReport']['FTP']['path'])
        except KeyError:
            webpath = "http://www.weewx.com"

        # station holds info such as 'altitude', 'latitude', etc. It seldom changes
        self.station = weewx.station.Station(self.stn_info, webpath, self.formatter, self.converter, self.skin_dict)
        
    def initAlmanac(self, celestial_ts):
        """ Initialize an instance of weeutil.Almanac.Almanac for the station's
        lat and lon, and for a specific time.
        
        celestial_ts: The timestamp of the time for which the Almanac is to
        be initialized."""
                
        # For better accuracy, the almanac requires the current temperature and barometric
        # pressure, so retrieve them from the default archive, using celestial_ts
        # as the time
        
        temperature_C = pressure_mbar = None

        archivedb = self._getArchive(self.skin_dict['archive_database'])
        if not celestial_ts:
            celestial_ts = archivedb.lastGoodStamp()
        rec = self.getRecord(archivedb, celestial_ts)

        if rec is not None:
            if rec.has_key('outTemp') :  temperature_C = rec['outTemp'].degree_C.raw 
            if rec.has_key('barometer'): pressure_mbar = rec['barometer'].mbar.raw
        if temperature_C is None: temperature_C = 15.0
        if pressure_mbar is None: pressure_mbar = 1010.0

        self.moonphases = self.skin_dict['Almanac'].get('moon_phases')

        altitude_vt = weewx.units.convert(self.station.altitude_vt, "meter")
        
        self.almanac = weewx.almanac.Almanac(celestial_ts, 
                                             self.station.latitude_f, 
                                             self.station.longitude_f,
                                             altitude_vt[0],
                                             temperature_C,
                                             pressure_mbar,
                                             self.moonphases,
                                             self.formatter)

    def getRecord(self, archivedb, time_ts):
        """Get an observation record from the archive database, returning
        it as a ValueDict."""

        # Get the record...:
        record_dict = archivedb.getRecord(time_ts)
        # ... convert to a dictionary with ValueTuples as values...
        record_dict_vt = weewx.units.dictFromStd(record_dict)
        # ... then wrap it in a ValueDict:
        record_vd = weewx.units.ValueDict(record_dict_vt, context='current', 
                                           formatter=self.formatter, converter=self.converter)
        
        return record_vd

    def generateSummaryBy(self, by_time, gen_ts):
        """This entry point is used for "SummaryBy" reports, such as NOAA monthly
        or yearly reports.
        
        by_time: "SummaryByMonth" to run the template for each month between start_ts and stop_ts. 
                 "SummaryByYear"  to run the template for each year  between start_ts and stop_ts. 
        
        gen_ts: The summary will be current as of this timestamp.
        """
        
        if by_time == 'SummaryByMonth':
            _genfunc = weeutil.weeutil.genMonthSpans
        elif by_time == 'SummaryByYear':
            _genfunc = weeutil.weeutil.genYearSpans
        else:
            syslog.syslog(syslog.LOG_NOTICE, "filegenerator: Unrecognized summary interval: %s. Skipped." % by_time)
            return

        for subreport in self.skin_dict['FileGenerator'][by_time].sections:
    
            (template, statsdb, archivedb, destination_dir, encoding) = self._prepGen(self.skin_dict['FileGenerator'][by_time][subreport])

            start_ts = archivedb.firstGoodStamp()
            if not start_ts:
                syslog.syslog(syslog.LOG_NOTICE, "filegenerator: No data for summary interval %s for subreport %s" % (by_time, subreport))
                return
            stop_ts  = gen_ts if gen_ts else archivedb.lastGoodStamp()
            
            ngen = 0
            t1 = time.time()

            # Loop through each timespan in the summary period
            for timespan in _genfunc(start_ts, stop_ts):

                #===============================================================
                # Calculate the destination filename using the template name.
                # Replace 'YYYY' with the year, 'MM' with the month, and
                # strip off the trailing '.tmpl':
                #===============================================================
                
                # Start by getting the start time as a timetuple.
                timespan_start_tt = time.localtime(timespan.start)
                # Get a string representing the year (e.g., '2009'):
                _yr_str = "%4d"  % timespan_start_tt[0]
                # Replace any instances of 'YYYY' with the string
                _filename = os.path.basename(template).replace('.tmpl','').replace('YYYY', _yr_str)
                if by_time == 'SummaryByMonth' :
                    # If this is a summary by month, do something similar for them month 
                    _mo_str = "%02d" % timespan_start_tt[1]
                    _filename = _filename.replace('MM', _mo_str)
                    # Save the resultant Year-Months so they can be used in an HTML drop down list:
                    self.outputted_dict['SummaryByMonth'].append("%s-%s" %(_yr_str, _mo_str))
                elif by_time == 'SummaryByYear' :
                    # Save the resultant years so they can be used in an HTML drop down list:
                    self.outputted_dict['SummaryByYear'].append(_yr_str)

                _fullpath = os.path.join(destination_dir, _filename)
    
                # If the file doesn't exist, or it is the last month, then
                # we must generate it
                if not os.path.exists(_fullpath) or timespan.includesArchiveTime(stop_ts):
    
                    searchList = self.getCommonSearchList(archivedb, statsdb, timespan) + self.getSummaryBySearchList(archivedb, statsdb, timespan)
                    #===================================================================
                    # Cheetah will use introspection on the searchList to populate the
                    # parameters in the template file.
                    # ===================================================================
                    text = Cheetah.Template.Template(file       = template,
                                                     searchList = searchList + [{'encoding' : encoding}],
                                                     filter     = encoding,
                                                     filtersLib = weewx.filegenerator)
                    # Open up the file that is to be created:
                    _file = open(_fullpath, mode='w')
                    try:
                        # Write it out
                        print >> _file, text
                    except Cheetah.NameMapper.NotFound, e:
                        (cl, unused_ob, unused_tr) = sys.exc_info()
                        syslog.syslog(syslog.LOG_ERR, """filegenerator: Caught exception "%s" """ % cl) 
                        syslog.syslog(syslog.LOG_ERR, """         ****  Message: "%s in template %s" """ % (e, template))
                        syslog.syslog(syslog.LOG_ERR, """         ****  Ignoring template and continuing.""")
                    else:
                        ngen += 1
                    finally:
                        # Close it
                        _file.close()
            
            t2 = time.time()
            elapsed_time = t2 - t1
            syslog.syslog(syslog.LOG_INFO, """filegenerator: generated %d '%s' files in %.2f seconds""" % (ngen, by_time, elapsed_time))

    def generateToDate(self, gen_ts):
        """This entry point is used for "To Date" reports, such as observations for
        this day, week, month, year, etc.
        
        gen_ts: A timestamp. The HTML files generated will be current as of
        this time."""
        
        ngen = 0
        t1 = time.time()

        for subreport in self.skin_dict['FileGenerator']['ToDate'].sections:
    
            (template, statsdb, archivedb, destination_dir, encoding) = self._prepGen(self.skin_dict['FileGenerator']['ToDate'][subreport])
            
            start_ts = archivedb.firstGoodStamp()
            if not start_ts:
                syslog.syslog(syslog.LOG_NOTICE, "filegenerator: No data for subreport %s" % (subreport,))
                return
            stop_ts  = gen_ts if gen_ts else archivedb.lastGoodStamp()
            
            timespan = weeutil.weeutil.TimeSpan(start_ts, stop_ts)
            
            searchList = self.getCommonSearchList(archivedb, statsdb, timespan) + self.getToDateSearchList(archivedb, statsdb, timespan)
            
            # Form the destination filename:
            _fullpath = os.path.basename(template).replace('.tmpl','')
    
            #===================================================================
            # Cheetah will use introspection on the searchList to populate the
            # parameters in the template file.
            # ===================================================================
            text = Cheetah.Template.Template(file       = template,
                                             searchList = searchList + [{'encoding' : encoding}],
                                             filter     = encoding,
                                             filtersLib = weewx.filegenerator)

            _file = open(os.path.join(destination_dir, _fullpath), mode='w')
            try:
                # Write it out
                print >> _file, text
            except Cheetah.NameMapper.NotFound, e:
                (cl, unused_ob, unused_tr) = sys.exc_info()
                syslog.syslog(syslog.LOG_ERR, """filegenerator: Caught exception "%s" """ % cl) 
                syslog.syslog(syslog.LOG_ERR, """         ****  Message: "%s in template %s" """ % (e, template))
                syslog.syslog(syslog.LOG_ERR, """         ****  Ignoring template and continuing.""")
            else:
                ngen += 1
            finally:
                # Close it
                _file.close()
                    
        elapsed_time = time.time() - t1
        syslog.syslog(syslog.LOG_INFO, "filegenerator: generated %d 'toDate' files in %.2f seconds" % (ngen, elapsed_time))
    
    def getSummaryBySearchList(self, archivedb, statsdb, timespan):
        """Return the searchList for the Cheetah Template engine for "summarize by" reports.
        
        Can easily be overridden to add things to the search list."""

        timespan_start_tt = time.localtime(timespan.start)

        searchList = [{'month_name' : time.strftime("%b", timespan_start_tt),
                       'year_name'  : timespan_start_tt[0]}]

        return searchList

    def getToDateSearchList(self, archivedb, statsdb, timespan):
        """Return the searchList for the Cheetah Template engine for "to date" generation.
        
        Can easily be overridden to add things to the search list."""

        currentRec = self.getRecord(archivedb, timespan.stop)
        searchList = [self.outputted_dict,
                      {'current' : currentRec}] 

        return searchList

    def getCommonSearchList(self, archivedb, statsdb, timespan):
        """Assemble the common searchList elements to be used by both the "ToDate" and
        "SummaryBy" reports.
        
        Can easily be overridden to add things to the common search list."""

        heatbase = self.skin_dict['Units']['DegreeDays'].get('heating_base')
        coolbase = self.skin_dict['Units']['DegreeDays'].get('heating_base')
        heatbase_t = (float(heatbase[0]), heatbase[1], "group_temperature") if heatbase else default_heatbase
        coolbase_t = (float(coolbase[0]), coolbase[1], "group_temperature") if coolbase else default_coolbase

        # Get a TaggedStats structure. This allows constructs such as
        # stats.month.outTemp.max
        stats = weewx.stats.TaggedStats(statsdb,
                                        timespan.stop,
                                        formatter = self.formatter,
                                        converter = self.converter,
                                        rain_year_start = self.station.rain_year_start,
                                        heatbase = heatbase_t,
                                        coolbase = coolbase_t)
        
        # IF the user has supplied an '[Extras]' section in the skin dictionary, include
        # it in the search list. Otherwise, just include an empty dictionary.
        extra_dict = self.skin_dict['Extras'] if self.skin_dict.has_key('Extras') else {}

        # Put together the search list:
        searchList = [{'station'    : self.station,
                       'almanac'    : self.almanac,
                       'unit'       : self.unitInfoHelper,
                       'heatbase'   : heatbase_t,
                       'coolbase'   : coolbase_t,
                       'Extras'     : extra_dict},
                       stats]
        return searchList
            
    def _prepGen(self, subskin_dict):
        """Gather the options together for a specific report, then
        retrieve the template file, stats database, archive database, the destination directory,
        and the encoding from those options."""
        
        # Walk the tree back to the root, accumulating options:
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

#===============================================================================
#                 Filters used for encoding
#===============================================================================

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

