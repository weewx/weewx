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

import Cheetah.Template
import Cheetah.Filters

import weeutil.Almanac
import weeutil.weeutil
import weewx.archive
import weewx.reportengine
import weewx.station
import weewx.stats
import weewx.units

# Default base temperature and unit type for heating and cooling degree days
# as a value tuple
default_heatbase = (65.0, "degree_F", "group_temperature")
default_coolbase = (65.0, "degree_F", "group_temperature")

#===============================================================================
#                    Class FileGenerator
#===============================================================================

class FileGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the template based generators"""
    
    def run(self):

        self.outputted_dict = {'SummaryByMonth' : [],
                               'SummaryByYear'  : []}
        
        self.initStation()
        self.initStats()
        self.initUnits()
        currentRec = self.getCurrentRec()
        self.initAlmanac(self.stop_ts)
        
        self.generateSummaryBy('SummaryByMonth', self.start_ts, self.stop_ts)
        self.generateSummaryBy('SummaryByYear',  self.start_ts, self.stop_ts)
        self.generateToDate(currentRec, self.stop_ts)

    def initStation(self):

        # station holds info such as 'altitude', 'latitude', etc. It seldom changes
        self.station = weewx.station.Station(self.config_dict, self.skin_dict)
        
    def initStats(self):

        # Open up the stats database:
        statsFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                     self.config_dict['Stats']['stats_file'])
        self.statsdb = weewx.stats.StatsReadonlyDb(statsFilename)
    
    def initUnits(self):
        
        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)
        self.unitInfoHelper = weewx.units.UnitInfoHelper(self.formatter, self.converter)
        
    def getCurrentRec(self):

        # Open up the main database archive
        archiveFilename = os.path.join(self.config_dict['Station']['WEEWX_ROOT'], 
                                       self.config_dict['Archive']['archive_file'])
        archive = weewx.archive.Archive(archiveFilename)
    
        self.stop_ts  = archive.lastGoodStamp() if self.gen_ts is None else self.gen_ts
        self.start_ts = archive.firstGoodStamp()
        
        # Get a dictionary with the current record:
        current_dict = archive.getRecord(self.stop_ts)
        # Convert to a dictionary with ValueTuples as values:
        current_dict_vt = weewx.units.dictFromStd(current_dict)
        # Now wrap it in a ValueDict:
        currentRec = weewx.units.ValueDict(current_dict_vt, context='current', 
                                           formatter=self.formatter, converter=self.converter)
        
        return currentRec

    def generateSummaryBy(self, by_time, start_ts, stop_ts):
        """This entry point is used for "SummaryBy" reports, such as NOAA monthly
        or yearly reports.
        
        by_time: Set to "SummaryByMonth" to run the template for each month between
        start_ts and stop_ts. Set to "SummaryByYear" for each year.
        
        start_ts: The first timestamp to be included.
        
        stop_ts: The last timestamp to be included.
        """
        
        if by_time == 'SummaryByMonth':
            _genfunc = weeutil.weeutil.genMonthSpans
        elif by_time == 'SummaryByYear':
            _genfunc = weeutil.weeutil.genYearSpans
        else:
            syslog.syslog(syslog.LOG_NOTICE, "filegenerator: Unrecognized summary interval: %s. Skipped." % by_time)
            return

        for subreport in self.skin_dict['FileGenerator'][by_time].sections:
    
            (template, destination_dir, encoding) = self._prepGen(self.skin_dict['FileGenerator'][by_time][subreport])

            ngen = 0
            t1 = time.time()

            # Loop through each timespan in the summary period
            for timespan in _genfunc(start_ts, stop_ts):

                # Get the start time as a timetuple.
                timespan_start_tt = time.localtime(timespan.start)
                #===============================================================
                # Calculate the output filename
                #===============================================================
                # Form the destination filename from the template name, replacing 'YYYY' with
                # the year, 'MM' with the month, and strip off the trailing '.tmpl':
                _yr_str = "%4d"  % timespan_start_tt[0]
                _filename = os.path.basename(template).replace('.tmpl','').replace('YYYY', _yr_str) 
                if by_time == 'SummaryByMonth' :
                    _mo_str = "%02d" % timespan_start_tt[1]
                    _filename = _filename.replace('MM', _mo_str)
                    # Save the included Year-Months so they can be used in an HTML drop down list:
                    self.outputted_dict['SummaryByMonth'].append("%s-%s" %(_yr_str, _mo_str))
                elif by_time == 'SummaryByYear' :
                    # Save the included years so they can be used in an HTML drop down list:
                    self.outputted_dict['SummaryByYear'].append(_yr_str)

                _fullpath = os.path.join(destination_dir, _filename)
    
                # If the file doesn't exist, or it is the last month, then
                # we must generate it
                if not os.path.exists(_fullpath) or timespan.includesArchiveTime(stop_ts):
    
                    searchList = self.getSummaryBySearchList(timespan)
                    # Run everything through the template engine
                    text = Cheetah.Template.Template(file       = template,
                                                     searchList = searchList + [{'encoding' : encoding}],
                                                     filter     = encoding,
                                                     filtersLib = weewx.filegenerator)
                    # Open up the file that is to be created:
                    file = open(_fullpath, mode='w')
                    try:
                        # Write it out
                        print >> file, text
                    except Cheetah.NameMapper.NotFound, e:
                        (cl, unused_ob, unused_tr) = sys.exc_info()
                        syslog.syslog(syslog.LOG_ERR, """filegenerator: Caught exception "%s" """ % cl) 
                        syslog.syslog(syslog.LOG_ERR, """         ****  Message: "%s in template %s" """ % (e, template))
                        syslog.syslog(syslog.LOG_ERR, """         ****  Ignoring template and continuing.""")
                    else:
                        ngen += 1
                    finally:
                        # Close it
                        file.close()
            
            t2 = time.time()
            elapsed_time = t2 - t1
            syslog.syslog(syslog.LOG_INFO, """filegenerator: generated %d '%s' files in %.2f seconds""" % (ngen, by_time, elapsed_time))

    def generateToDate(self, currentRec, stop_ts):
        """This entry point is used for "To Date" reports, such as observations for
        this day, week, month, year, etc.
        
        currentRec: A dictionary containing current observation. Key is a type
        ('outTemp', 'barometer', etc.), value the value of the
        variable. Usually, this is an archive record.

        stop_ts: A timestamp. The HTML files generated will be current as of
        this time."""
        
        ngen = 0
        t1 = time.time()

        searchList = self.getToDateSearchList(currentRec, stop_ts)
            
        for subreport in self.skin_dict['FileGenerator']['ToDate'].sections:
    
            (template, destination_dir, encoding) = self._prepGen(self.skin_dict['FileGenerator']['ToDate'][subreport])
            
            # Form the destination filename:
            _fullpath = os.path.basename(template).replace('.tmpl','')
    
            #===================================================================
            # Here's where the heavy lifting occurs. Use Cheetah to actually
            # generate the files. It will use introspection on the searchList to
            # populate the parameters in the template file.
            # ===================================================================
            text = Cheetah.Template.Template(file       = template,
                                             searchList = searchList + [{'encoding' : encoding}],
                                             filter     = encoding,
                                             filtersLib = weewx.filegenerator)

            file = open(os.path.join(destination_dir, _fullpath), mode='w')
            try:
                # Write it out
                print >> file, text
            except Cheetah.NameMapper.NotFound, e:
                (cl, unused_ob, unused_tr) = sys.exc_info()
                syslog.syslog(syslog.LOG_ERR, """filegenerator: Caught exception "%s" """ % cl) 
                syslog.syslog(syslog.LOG_ERR, """         ****  Message: "%s in template %s" """ % (e, template))
                syslog.syslog(syslog.LOG_ERR, """         ****  Ignoring template and continuing.""")
            else:
                ngen += 1
            finally:
                # Close it
                file.close()
        
        elapsed_time = time.time() - t1
        syslog.syslog(syslog.LOG_INFO, "filegenerator: generated %d 'toDate' files in %.2f seconds" % (ngen, elapsed_time))
    
    def getSummaryBySearchList(self, timespan):
        """Return the searchList for the Cheetah Template engine for "summarize by" reports.
        
        Can easily be overridden to add things to the search list."""

        searchList = self.getCommonSearchList(timespan.stop)

        timespan_start_tt = time.localtime(timespan.start)

        searchList += [{'month_name' : time.strftime("%b", timespan_start_tt),
                        'year_name'  : timespan_start_tt[0]}]

        return searchList

    def getToDateSearchList(self, currentRec, stop_ts):
        """Return the searchList for the Cheetah Template engine for "to date" generation.
        
        Can easily be overridden to add things to the search list."""

        searchList = self.getCommonSearchList(stop_ts)

        searchList += [self.outputted_dict, 
                       {'current' : currentRec}] 

        return searchList

    def getCommonSearchList(self, stop_ts):
        """Assemble the common searchList elements to be used by both the "ToDate" and
        "SummaryBy" reports.
        
        Can easily be overridden to add things to the common search list."""

        heatbase = self.skin_dict['Units']['DegreeDays'].get('heating_base')
        coolbase = self.skin_dict['Units']['DegreeDays'].get('heating_base')
        heatbase_t = (float(heatbase[0]), heatbase[1], "group_temperature") if heatbase else default_heatbase
        coolbase_t = (float(coolbase[0]), coolbase[1], "group_temperature") if coolbase else default_coolbase

        # Get a TaggedStats structure. This allows constructs such as
        # stats.month.outTemp.max
        stats = weewx.stats.TaggedStats(self.statsdb,
                                        stop_ts,
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
            
    def initAlmanac(self, celestial_ts):
        """ Initialize an instance of weeutil.Almanac.Almanac for the station's
        lat and lon, and for a specific time.
        
        celestial_ts: The timestamp of the time for which the Almanac is to
        be initialized."""
        
        self.moonphases = self.skin_dict['Almanac'].get('moon_phases')

        # almanac holds celestial information (sunrise, phase of moon). Its celestial
        # data changes slowly.
        altitude_vt = weewx.units.convert(self.station.altitude_vt, "meter")
        self.almanac = weeutil.Almanac.Almanac(celestial_ts, 
                                               self.station.latitude_f, 
                                               self.station.longitude_f,
                                               altitude_vt[0],
                                               self.moonphases)

    def _prepGen(self, subskin_dict):
        
        accum_dict = weeutil.weeutil.accumulateLeaves(subskin_dict)
        template = os.path.join(self.config_dict['Station']['WEEWX_ROOT'],
                                self.config_dict['Reports']['SKIN_ROOT'],
                                accum_dict['skin'],
                                accum_dict['template'])
        destination_dir = os.path.join(self.config_dict['Station']['WEEWX_ROOT'],
                                       accum_dict['HTML_ROOT'],
                                       os.path.dirname(accum_dict['template']))
        encoding = accum_dict['encoding']

        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(destination_dir)
        except OSError:
            pass

        return (template, destination_dir, encoding)

#===============================================================================
#                 Filters used for encoding
#===============================================================================

class html_entities(Cheetah.Filters.Filter):

    def filter(self, val, **dummy_kw):
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

    def filter(self, val, **dummy_kw):
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

    def filter(self, val, **dummy_kw):
        """Filter incoming strings, converting to UTF-8"""
        if isinstance(val, unicode):
            filtered = val.encode('utf8')
        elif val is None:
            filtered = ''
        else:
            filtered = str(val)
        return filtered

