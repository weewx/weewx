#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

"""Example of how to extend a report generator.

This generator offers two extra tags:

    'alltime': All time statistics. For example, "what is the all time high temperature?"

    'seven_day': Statistics for the last seven days. That is, since midnight seven days
                 ago.

To use it, in the skin's generator_list, replace weewx.filegenerator.FileGenerator
with examples.mygenerator.MyFileGenerator.

You can then use tags such as $alltime.outTemp.max for the all-time max temperature,
or $seven_day.rain.sum for the total rainfall in the last seven days.
"""
import datetime
import time

from weewx.filegenerator import FileGenerator
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan

class MyFileGenerator(FileGenerator):                            # 1
  
    def getToDateSearchList(self, archivedb, statsdb, valid_timespan): # 2
        """Returns a search list with two additions. Overrides the
        default "getToDateSearchList" method.
        
        Parameters:
          archivedb: An instance of weewx.archive.Archive
          
          statsdb:   An instance of weewx.stats.StatsDb
          
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of 
                          valid times."""

        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object valid_timespan already holds all valid times to be
        # used in the report.
        all_stats = TimeSpanStats(valid_timespan,
                                  statsdb,
                                  formatter=self.formatter,
                                  converter=self.converter)         # 3
        
        # Now get a TimeSpanStats object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(valid_timespan.stop) - datetime.timedelta(weeks=1)    #4
        # Now convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())                  # 5
        # Now form a TimeSpanStats object, using the time span we just calculated:
        seven_day_stats = TimeSpanStats(TimeSpan(week_ts, valid_timespan.stop),
                                        statsdb,
                                        formatter=self.formatter,
                                        converter=self.converter)   #6

        # Get the superclass's search list:       
        search_list = FileGenerator.getToDateSearchList(self, archivedb, statsdb, valid_timespan) # 7

        # Now tack on my two additions as a small dictionary with keys 'alltime' and 'seven_day':
        search_list += [ {'alltime'   : all_stats,
                          'seven_day' : seven_day_stats} ]               # 8
        
        return search_list

