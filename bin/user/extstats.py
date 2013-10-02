# alltime generator
# based on the mygenerator example in the weewx distribution

"""Extension to provide cheetah generator with additional statistics.

This extension provides the following variables:

  'alltime': All time statistics. For example, "what is the all time high
             temperature?"

  'seven_day': Statistics for the last seven days. That is, since midnight
               seven days ago.

To install, add this to the search list extensions:

[FileGenerator]
    search_list_extensions = user.extstats.ExtStatsVariables

You can then use tags such as $alltime.outTemp.max for the all-time max
temperature, or $seven_day.rain.sum for the total rainfall in the last
seven days.
"""
import datetime
import time

from user.cheetahgenerator import SearchList
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan

class ExtStatsVariables(SearchList):
    def __init__(self, generator):
        self.formatter = generator.formatter
        self.converter = generator.converter

    def getSearchList(self, timespan, archivedb, statsdb):
        """Returns a search list with two entries.

        Parameters:
          timespan:  An instance of weeutil.weeutil.TimeSpan. This will
                     hold the start and stop times of the domain of 
                     valid times.

          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb
        """

        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object timespan already holds all valid times
        # to be used in the report.
        all_stats = TimeSpanStats(timespan,
                                  statsdb,
                                  formatter=self.formatter,
                                  converter=self.converter)

        # Now get a TimeSpanStats object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(timespan.stop) - datetime.timedelta(weeks=1)
        # Now convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())
        # Now form a TimeSpanStats object, using the time span we just
        # calculated:
        seven_day_stats = TimeSpanStats(TimeSpan(week_ts, timespan.stop),
                                        statsdb,
                                        formatter=self.formatter,
                                        converter=self.converter)

        # The search list is a small dictionary with the keys
        # 'alltime' and 'seven_day':
        search_list = [ {'alltime'   : all_stats,
                         'seven_day' : seven_day_stats} ]

        return search_list
