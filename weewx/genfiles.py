#
#    Copyright (c) 2009 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Generate files from templates.

This basically includes NOAA summary reports, and HTML files."""

import os.path
import re
import syslog
import time

import Cheetah.Template

import weewx
import weewx.formatter
import weewx.station
import weewx.stats
import weewx.units
import weeutil.Almanac
import weeutil.weeutil

class GenFiles(object):
    """Base class for generator classes that generate files"""
    
    def __init__(self, report_dict):
        self.report_dict = report_dict
        self.initStation(report_dict)
        self.initStats(report_dict)
        self.initUnits(report_dict)

    def initStation(self, report_dict):
        # station holds info such as 'altitude', 'latitude', etc. It seldom changes
        self.station = weewx.station.Station(report_dict)
        
    def initStats(self, report_dict):
        # Open up the stats database:
        statsFilename = os.path.join(report_dict['Station']['WEEWX_ROOT'], 
                                     report_dict['Stats']['stats_file'])
        self.statsdb = weewx.stats.StatsReadonlyDb(statsFilename,
                                                  float(report_dict['Station'].get('heating_base', '65')),
                                                  float(report_dict['Station'].get('cooling_base', '65')))
    
    def initUnits(self, report_dict):
        self.unitTypeDict = weewx.units.getUnitTypeDict(report_dict)
        
    def _prepGen(self, subreport_dict):
        
        accum_dict = weeutil.weeutil.accumulateLeaves(subreport_dict)

        template = os.path.join(self.report_dict['Station']['WEEWX_ROOT'],
                                self.report_dict['Reports']['SKIN_ROOT'],
                                accum_dict['skin'],
                                accum_dict['template'])
        destination_dir = os.path.join(self.report_dict['Station']['WEEWX_ROOT'],
                                       self.report_dict['Reports']['HTML_ROOT'],
                                       accum_dict['destination_dir'])
        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(destination_dir)
        except OSError:
            pass

        return (template, destination_dir)
    
class GenByMonth(GenFiles):
    """Class for generating reports that run 'by month.'"""

    def generate(self, start_ts, stop_ts):
        
        for subreport in self.report_dict['ByMonth'].sections:
            print "starting GenByMonth subreport ", subreport
    
            (template, destination_dir) = self._prepGen(self.report_dict['ByMonth'][subreport])

            ngen = 0
            t1 = time.time()
            
            # Loop through all months, looking for reports that need to be
            # generated.
            for monthSpan in weeutil.weeutil.genMonthSpans(start_ts, stop_ts):
                # Calculate the file name for this month
                _month_start_tt = time.localtime(monthSpan.start)
                _filename = os.path.basename(template).replace('YYYY', "%4d" % _month_start_tt[0]).replace('MM', "%02d" % _month_start_tt[1]).replace('.tmpl','')
                _fullpath = os.path.join(destination_dir, _filename)
                print "ByMonth output will go to path ", _fullpath
    
                # If the file doesn't exist, or it is the last month, then
                # we must generate it
                if not os.path.exists(_fullpath) or monthSpan.includesArchiveTime(stop_ts):
    
                    searchList = self.getSearchList(monthSpan)
                    # Run everything through the template engine
                    text = Cheetah.Template.Template(file = template, searchList = searchList)
                    # Open up the file that is to be created:
                    file = open(_fullpath, mode='w')
                    # Write it out
                    print >> file, text
                    # Close it
                    file.close()
                    ngen += 1
            
            t2 = time.time()
            elapsed_time = t2 - t1
            syslog.syslog(syslog.LOG_INFO, """genfiles: generated %d "ByMonth" files in %.2f seconds""" % (ngen, elapsed_time))

    def getSearchList(self, monthSpan):
        """Return the searchList for the Cheetah Template engine for month NOAA reports.
        
        Can easily be overridden to add things to the search list.
        """
        month_start_tt = time.localtime(monthSpan.start)
        # Form a suitable name for the month:
        (_yr, _mo) = month_start_tt[0:2]
        monthName = time.strftime("%b", month_start_tt)

        # Get the stats for this month from the database:
        monthStats = weewx.stats.TimespanStats(self.statsdb, monthSpan, self.unitTypeDict)
        
        searchList = [{'station'      : self.station,
                       'year_name'    : _yr,
                       'month_name'   : monthName,
                       'month'        : monthStats}]
        return searchList

class GenByYear(GenFiles):
    """Class for generating reports that run 'by year.'"""
    
    def generate(self, start_ts, stop_ts):
        for subreport in self.report_dict['ByYear'].sections:
            print "starting GenByYear subreport ", subreport
    
            (template, destination_dir) = self._prepGen(self.report_dict['ByYear'][subreport])

            ngen = 0
            t1 = time.time()
            
            # Loop through all months, looking for reports that need to be
            # generated.
            for yearSpan in weeutil.weeutil.genYearSpans(start_ts, stop_ts):
                # Calculate the file name for this month
                _month_start_tt = time.localtime(yearSpan.start)
                _filename = os.path.basename(template).replace('YYYY', "%4d" % _month_start_tt[0]).replace('.tmpl','')
                _fullpath = os.path.join(destination_dir, _filename)
                print "ByYear output will go to path ", _fullpath
    
                # If the file doesn't exist, or it is the last month, then
                # we must generate it
                if not os.path.exists(_fullpath) or yearSpan.includesArchiveTime(stop_ts):
    
                    searchList = self.getSearchList(yearSpan)
                    # Run everything through the template engine
                    text = Cheetah.Template.Template(file = template, searchList = searchList)
                    # Open up the file that is to be created:
                    file = open(_fullpath, mode='w')
                    # Write it out
                    print >> file, text
                    # Close it
                    file.close()
                    ngen += 1
            
            t2 = time.time()
            elapsed_time = t2 - t1
            syslog.syslog(syslog.LOG_INFO, """genfiles: generated %d "ByYear" files in %.2f seconds""" % (ngen, elapsed_time))

    def getSearchList(self, yearSpan):
        """Return the searchList for the Cheetah Template engine for By Year reports.
        
        Can easily be overridden to add things to the search list.
        """

        _yr = time.localtime(yearSpan.start)[0]
                
        yearStats = weewx.stats.TimespanStats(self.statsdb, yearSpan, self.unitTypeDict)

        searchList = [{'station'   : self.station,
                       'year_name' : _yr,
                       'year'      : yearStats}]
        
        return searchList

class GenToDate(GenFiles):
    """Class for generating "to date" reports, such as daily, weekly, monthly,
    and yearly summaries."""
    
    def generate(self, currentRec, stop_ts):
        """
        currentRec: A dictionary containing current observation. Key is a type
        ('outTemp', 'barometer', etc.), value the value of the
        variable. Usually, this is an archive record.

        stop_ts: A timestamp. The HTML files generated will be current as of
        this time."""
        
        
        ngen = 0
        t1 = time.time()

        # Get an appropriate formatter:
        self.formatter =  weewx.formatter.Formatter(weewx.units.getStringFormatDict(self.report_dict),
                                                    weewx.units.getHTMLLabelDict(self.report_dict),
                                                    self.report_dict['Labels']['Time'])

        self.initAlmanac(stop_ts)
    
        searchList = self.getSearchList(currentRec, stop_ts)
            
        for subreport in self.report_dict['ToDate'].sections:
            print "starting GenToDate subreport ", subreport
    
            (template, destination_dir) = self._prepGen(self.report_dict['ToDate'][subreport])

            print "GenToDate template is ", template, "; destination dir is ", destination_dir
    
            #===================================================================
            # Here's where the heavy lifting occurs. Use Cheetah to actually
            # generate the files. It will use introspection on the searchList to
            # populate the parameters in the template file.
            # ===================================================================
            html = Cheetah.Template.Template(file = template, searchList = searchList)

            file = open(os.path.join(self.html_dir, template + ".html"), mode='w')
            print >> file, html
            ngen += 1
        
        elapsed_time = time.time() - t1
        syslog.syslog(syslog.LOG_INFO, "genhtml: generated %d 'toDate' pages in %.2f seconds" % (ngen, elapsed_time))
    
    def initAlmanac(self, celestial_ts):
        """ Initialize an instance of weeutil.Almanac.Almanac for the station's
        lat and lon, and for a specific time.
        
        celestial_ts: The timestamp of the time for which the Almanac is to
        be initialized.
        """
        self.moonphases = self.report_dict['Almanac'].get('moon_phases')

        # almanac holds celestial information (sunrise, phase of moon). Its celestial
        # data slowly changes.
        self.almanac = weeutil.Almanac.Almanac(celestial_ts, 
                                               self.station.latitude_f, 
                                               self.station.longitude_f, 
                                               self.moonphases)
    



    def get_existing_NOAA_reports(self):
        """Returns strings with the dates for which NOAA reports exists.
        
        returns: a tuple. First value is the list of monthly reports,
        the second a list of yearly reports.
        """
        
        re_month = re.compile(r"NOAA-\d{4}-\d{2}\.txt")
        re_year  = re.compile(r"NOAA-\d{4}\.txt") 
        fileList = os.listdir(self.noaa_dir)
        fileList.sort()
        month_list = []
        year_list  = []
        for _file in fileList:
            if re_month.match(_file):
                month_list.append(_file[5:12])
            elif re_year.match(_file):
                year_list.append(_file[5:9])
        return (month_list, year_list)
    
    
    def getSearchList(self, currentRec, stop_ts):
        """Return the searchList for the Cheetah Template engine for HTML generation.
        
        Can easily be overridden to add things to the search list.
        """

        # Calculate the time ranges for all the desired time spans.
        daySpan      = weeutil.weeutil.archiveDaySpan(stop_ts)
        weekSpan     = weeutil.weeutil.archiveWeekSpan(stop_ts, startOfWeek = self.station.week_start)
        monthSpan    = weeutil.weeutil.archiveMonthSpan(stop_ts)
        yearSpan     = weeutil.weeutil.archiveYearSpan(stop_ts)
        rainYearSpan = weeutil.weeutil.archiveRainYearSpan(stop_ts, self.station.rain_year_start)

        # Assemble the dictionary that will be given to the template engine:
        stats = {}
        stats['current']  = currentRec
        stats['day']      = weewx.stats.TimespanStats(self.statsdb, daySpan,      self.unitTypeDict)
        stats['week']     = weewx.stats.TimespanStats(self.statsdb, weekSpan,     self.unitTypeDict)
        stats['month']    = weewx.stats.TimespanStats(self.statsdb, monthSpan,    self.unitTypeDict)
        stats['year']     = weewx.stats.TimespanStats(self.statsdb, yearSpan,     self.unitTypeDict)
        stats['rainyear'] = weewx.stats.TimespanStats(self.statsdb, rainYearSpan, self.unitTypeDict)

        # Get a formatted view into the statistical information.
        statsFormatter = weewx.formatter.ModelFormatter(stats, self.formatter)
        
        # Get the list of dates for which NOAA monthly and yearly reports are available:
        NOAA_month_list, NOAA_year_list = self.get_existing_NOAA_reports()

        searchList = [{'station'         : self.station,
                       'almanac'         : self.almanac,
                       'NOAA_month_list' : NOAA_month_list,
                       'NOAA_year_list'  : NOAA_year_list},
                       statsFormatter]

        return searchList
    
