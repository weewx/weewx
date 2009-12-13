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

import time
import re
import os.path
import datetime
import syslog

import Cheetah.Template

import weewx
import weewx.stats
import weewx.station
import weewx.formatter
import weeutil.weeutil

class GenFiles(object):
    """Manages the generation of NOAA and HTML files
    
    This class has been designed so that it's easy to subclass and override majob
    pieces of functionality."""
    
    def __init__(self, config_dict):

        self.initStation(config_dict)
        self.initStats(config_dict)
        self.initNoaa(config_dict)
        self.initHtml(config_dict)
        self.moonphases = config_dict['Almanac'].get('moon_phases')
        self.cache = {}

    def initStation(self, config_dict):
        # station holds info such as 'altitude', 'latitude', etc. It seldom changes
        self.station = weewx.station.Station(config_dict)
        
    def initStats(self, config_dict):
        # Open up the stats database:
        statsFilename = os.path.join(config_dict['Station']['WEEWX_ROOT'], 
                                     config_dict['Stats']['stats_file'])
        self.statsdb = weewx.stats.StatsDb(statsFilename,
                                           int(config_dict['Station'].get('heating_base', 65)),
                                           int(config_dict['Station'].get('cooling_base', 65)))
    
        
    def initNoaa(self, config_dict):
        # Get the directory holding the NOAA templates
        self.noaa_template_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                              config_dict['NOAA'].get('template_root', 'templates'))
    
        # Get the directory that will hold the generated NOAA reports:
        self.noaa_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                     config_dict['NOAA'].get('noaa_dir', 'public_html/NOAA'))

        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(self.noaa_dir)
        except OSError:
            pass

    
    def initHtml(self, config_dict):

        # Get the directory holding the templates
        self.html_template_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                              config_dict['HTML'].get('template_root', 'templates'))
        # Get the directories that will hold the generated HTML files:
        self.html_dir = os.path.join(config_dict['Station']['WEEWX_ROOT'],
                                     config_dict['HTML'].get('html_root', 'public_html'))

        # Get an appropriate formatter:
        self.formatter =  weewx.formatter.Formatter(config_dict['Labels']['ImperialFormats'],
                                                    config_dict['HTML']['ImperialUnits'],
                                                    config_dict['HTML']['Time'])

        try:
            # Create the directory that is to receive the generated files.  If
            # it already exists an exception will be thrown, so be prepared to
            # catch it.
            os.makedirs(self.html_dir)
        except OSError:
            pass

        self.template_list = ('index', 'week', 'month', 'year')

    def initAlmanac(self, celestial_ts):
        # almanac holds celestial information (sunrise, phase of moon). Its celestial
        # data slowly changes.
        self.almanac = weeutil.Almanac.Almanac(celestial_ts, 
                                               self.station.latitude_f, 
                                               self.station.longitude_f, 
                                               self.moonphases)
    
    def generateNoaa(self, start_ts, stop_ts):
        """ Generate NOAA yearly and monthly reports.

        start_ts: A timestamp within the year of the first report to be generated.

        stop_ts: A timestamp within the year of the last report to be generated."""
        
        self.generateNoaaYears(start_ts, stop_ts)
        self.generateNoaaMonths(start_ts, stop_ts)
        
    def generateNoaaYears(self, start_ts, stop_ts):
        """ Generate NOAA yearly reports.

        start_ts: A timestamp within the year of the first report to be
        generated.

        stop_ts: A timestamp within the year of the last report to be
        generated."""


        ngen = 0
        t1 = time.time()
        
        # This is the template to be used to generate the yearly reports:
        noaa_year_template_file = os.path.join(self.noaa_template_dir, "NOAA_year.tmpl")
        
        # Loop through all months, looking for reports that need to be
        # generated.
        for yearSpan in weeutil.weeutil.genYearSpans(start_ts, stop_ts):

            _yr = time.localtime(yearSpan.start)[0]
            _filename = "NOAA-%d.txt" % _yr
            _fullpath = os.path.join(self.noaa_dir, _filename)

            # If the file doesn't exist, or it is the last year, then
            # we must generate it
            if not os.path.exists(_fullpath) or yearSpan.includesArchiveTime(stop_ts):

                searchList = self.get_Year_SearchList(yearSpan, stop_ts)
                
                # Run everything through the template engine
                text = Cheetah.Template.Template(file = noaa_year_template_file, searchList = searchList)
                # Open up the file that is to be created:
                file = open(_fullpath, mode='w')
                # Write it out
                print >> file, text
                # Close it
                file.close()
                ngen += 1
        
        t2 = time.time()
        elapsed_time = t2 - t1
        syslog.syslog(syslog.LOG_INFO, "gennoaa: generated %d NOAA year files in %.2f seconds" % (ngen, elapsed_time))

    def generateNoaaMonths(self, start_ts, stop_ts):
        """ Generate NOAA monthly reports.

        start_ts: A timestamp within the month of the first report to be
        generated.

        stop_ts: A timestamp within the month of the last report to be
        generated."""

        ngen = 0
        t1 = time.time()
        
        # This is the template to be used to generate the monthly reports:
        noaa_month_template_file = os.path.join(self.noaa_template_dir, "NOAA_month.tmpl")
        
        # Loop through all months, looking for reports that need to be
        # generated.
        for monthSpan in weeutil.weeutil.genMonthSpans(start_ts, stop_ts):
            # Calculate the file name for this month
            _month_start_tt = time.localtime(monthSpan.start)
            _filename = "NOAA-%d-%02d.txt" % _month_start_tt[0:2]
            _fullpath = os.path.join(self.noaa_dir, _filename)

            # If the file doesn't exist, or it is the last month, then
            # we must generate it
            if not os.path.exists(_fullpath) or monthSpan.includesArchiveTime(stop_ts):

                searchList = self.get_Month_SearchList(monthSpan, stop_ts)
                # Run everything through the template engine
                text = Cheetah.Template.Template(file = noaa_month_template_file, searchList = searchList)
                # Open up the file that is to be created:
                file = open(_fullpath, mode='w')
                # Write it out
                print >> file, text
                # Close it
                file.close()
                ngen += 1
        
        t2 = time.time()
        elapsed_time = t2 - t1
        syslog.syslog(syslog.LOG_INFO, "gennoaa: generated %d NOAA monthly files in %.2f seconds" % (ngen, elapsed_time))

    def generateHtml(self, currentRec, stop_ts):
        """Generate HTML pages.

        currentRec: A dictionary containing current observation. Key is a type
        ('outTemp', 'barometer', etc.), value the value of the
        variable. Usually, this is an archive record.

        stop_ts: A timestamp. The HTML files generated will be current as of
        this time."""
        
        self.initAlmanac(stop_ts)

        searchList = self.get_Html_SearchList(currentRec, stop_ts)
        
        ngen = 0
        t1 = time.time()

        # Generate for each HTML template:
        for template in self.template_list:
    
            # Here's the full path to the template file:
            template_file = os.path.join(self.html_template_dir, template + ".tmpl")

            #===================================================================
            # Here's where the heavy lifting occurs. Use Cheetah to actually
            # generate the files. It will use introspection on the searchList to
            # populate the parameters in the template file.
            # ===================================================================
            html = Cheetah.Template.Template(file = template_file, searchList = searchList)

            file = open(os.path.join(self.html_dir, template + ".html"), mode='w')
            print >> file, html
            ngen += 1
    
        elapsed_time = time.time() - t1
        syslog.syslog(syslog.LOG_INFO, "genhtml: generated %d HTML pages in %.2f seconds" % (ngen, elapsed_time))


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
    
    def get_Year_SearchList(self, yearSpan, stop_ts):
        """Return the searchList for the Cheetah Template engine for year NOAA reports.
        
        Can easily be overridden to add things to the search list.
        """

        _yr = time.localtime(yearSpan.start)[0]
                
        # Get the stats for this year:
        yearStats = self._get_year(yearSpan, stop_ts)

        searchList = [{'station'   : self.station,
                       'year_name' : _yr,
                       'year'      : yearStats}]
        
        return searchList
        
    def get_Month_SearchList(self, monthSpan, stop_ts):
        """Return the searchList for the Cheetah Template engine for month NOAA reports.
        
        Can easily be overridden to add things to the search list.
        """
        month_start_tt = time.localtime(monthSpan.start)
        # Form a suitable name for the month:
        (_yr, _mo) = month_start_tt[0:2]
        monthName = time.strftime("%b", month_start_tt)

        # Get the stats for this month from the database:
        monthStats = self._get_month(monthSpan)
        
        searchList = [{'station'      : self.station,
                       'year_name'    : _yr,
                       'month_name'   : monthName,
                       'month'        : monthStats}]
        return searchList
    
    def get_Html_SearchList(self, currentRec, stop_ts):
        """Return the searchList for the Cheetah Template engine for HTML generation.
        
        Can easily be overridden to add things to the search list.
        """

        t1 = time.time()

        _date = datetime.date.fromtimestamp(stop_ts)
        # Form the dictionary that will hold the statistical summaries:
        stats = {}
        # Go get this year's data, then break it up into month and day
        weekSpan     = weeutil.weeutil.weekSpan(stop_ts)
        yearSpan     = weeutil.weeutil.yearSpan(stop_ts)
        rainYearSpan = weeutil.weeutil.rainYearSpan(stop_ts, self.station.rain_year_start)

        stats['year']     = self._get_year(yearSpan, stop_ts)
        stats['month']    = stats['year'].months[_date.month-1]
        stats['day']      = stats['month'].days[_date.day-1]
        stats['week']     = self.statsdb.week(weekSpan)
        stats['rainyear'] = self.statsdb.year(rainYearSpan)
        stats['current']  = currentRec

        # Get a view into the statistical information.
        statsView = weewx.formatter.ModelView(stats, self.formatter)
        
        # Get the list of dates for which NOAA monthly and yearly reports are available:
        NOAA_month_list, NOAA_year_list = self.get_existing_NOAA_reports()

        searchList = [{'station'         : self.station,
                       'almanac'         : self.almanac,
                       'NOAA_month_list' : NOAA_month_list,
                       'NOAA_year_list'  : NOAA_year_list},
                       statsView]
        elapsed_time = time.time() - t1
        syslog.syslog(syslog.LOG_DEBUG, "genhtml: assembled searchList for HTML generation in %.2f seconds" % (elapsed_time,))

        return searchList
    
    def _get_year(self, yearSpan, stop_ts):
        """Returns statistical data for a year, possibly from a cache.
        
        Returns from the cache if available, otherwise from the 
        stats database.
        
        It only puts the 'stop' year in the database, so as to avoid
        memory bloat (it's the one that gets used over and over).
        """
        yearStats = self.cache.get(yearSpan)
        if not yearStats:
            yearStats = self.statsdb.year(yearSpan)
            if yearSpan.includesArchiveTime(stop_ts):
                self.cache[yearSpan] = yearStats
        return yearStats

    def _get_month(self, monthSpan):
        """Returns statistical data for a month, possibly from a cache.
        
        Returns from the cache if available, otherwise from the 
        stats database."""
        
        # Search for the containing year:
        yearSpan = weeutil.weeutil.yearSpan(monthSpan.start)
        yearStats = self.cache.get(yearSpan)
        if yearStats:
            # The containing year was found. Extract the month.
            _date = datetime.date.fromtimestamp(monthSpan.start)
            return yearStats.months[_date.month-1]

        # Cache miss. Get the data from the stats database. Don't store
        # it, because it's unlikely that the month will be requested
        # again w/o the year also being requested.
        return self.statsdb.month(monthSpan)
