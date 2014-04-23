# ext stats based on the xsearch example
# $Id$
# Copyright 2013 Matthew Wall, all rights reserved

"""This search list extension offers extra tags:

  'alltime':    All time statistics.

  'seven_day':  Statistics for the last seven days. 

  'thirty_day': Statistics for the last thirty days.

You can then use tags such as $alltime.outTemp.max for the all-time max
temperature, or $seven_day.rain.sum for the total rainfall in the last seven
days, or $thirty_day.wind.max for maximum wind speed in the past thirty days.
"""
import datetime
import time

from weewx.cheetahgenerator import SearchList
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan

class ExtStats(SearchList):
    
    def __init__(self, generator):
        SearchList.__init__(self, generator)
  
    def get_extension(self, valid_span, archivedb, statsdb):
        """Returns a search list extension with additions.

          valid_span: An instance of weeutil.weeutil.TimeSpan. This holds
                      the start and stop times of the domain of valid times.
          archivedb: An instance of weewx.archive.Archive          
          statsdb:   An instance of weewx.stats.StatsDb
        """

        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object valid_span already holds all valid times to be
        # used in the report.
        all_stats = TimeSpanStats(valid_span,
                                  statsdb,
                                  context='alltime',
                                  formatter=self.generator.formatter,
                                  converter=self.generator.converter)
        
        # Now get a TimeSpanStats object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(valid_span.stop) - datetime.timedelta(weeks=1)
        # Now convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())
        # Now form a TimeSpanStats object, using the time span just calculated:
        seven_day_stats = TimeSpanStats(TimeSpan(week_ts, valid_span.stop),
                                        statsdb,
                                        context='seven_day',
                                        formatter=self.generator.formatter,
                                        converter=self.generator.converter)

        # Now use a similar process to get statistics for the last 30 days.
        days_dt = datetime.date.fromtimestamp(valid_span.stop) - datetime.timedelta(days=30)
        days_ts = time.mktime(days_dt.timetuple())
        thirty_day_stats = TimeSpanStats(TimeSpan(days_ts, valid_span.stop),
                                         statsdb,
                                         context='thirty_day',
                                         formatter=self.generator.formatter,
                                         converter=self.generator.converter)

        return { 'alltime'   : all_stats,
                 'seven_day' : seven_day_stats,
                 'thirty_day': thirty_day_stats }
