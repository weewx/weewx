#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Example of how to extend the search list used by the Cheetah generator.

This search list extension offers two extra tags:

    'alltime':   All time statistics.
                 For example, "what is the all time high temperature?"

    'seven_day': Statistics for the last seven days.
                 That is, since midnight seven days ago.

To use it, modify the option search_list in your skin.conf configuration file,
adding the name of this extension. For this example, the name of the extension
is examples.xsearch.MyXSearch. So, when you're done, it will look something
like this:

[CheetahGenerator]
    search_list_extensions = examples.xsearch.MyXSearch

Note that if your file skin.conf is from an older version of Weewx, this
section may be named [FileGenerator]. It will work just fine.

You can then use tags such as $alltime.outTemp.max for the all-time max
temperature, or $seven_day.rain.sum for the total rainfall in the last
seven days.
"""
import datetime
import time

from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan

class MyXSearch(SearchList):                                                 # 1
    """My search list extension"""

    def __init__(self, generator):                                           # 2
        SearchList.__init__(self, generator)
    
    def get_extension_list(self, timespan, db_lookup):                       # 3
        """Returns a search list extension with two additions.
        
        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of 
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
        """

        # First, create TimespanBinder object for all time. This one is easy
        # because the object timespan already holds all valid times to be
        # used in the report.
        all_stats = TimespanBinder(timespan, 
                                   db_lookup,
                                   formatter=self.generator.formatter,
                                   converter=self.generator.converter)       # 4
        
        # Now get a TimespanBinder object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(timespan.stop) - \
                    datetime.timedelta(weeks=1)                              # 5
        # Convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())                           # 6
        # Form a TimespanBinder object, using the time span we just
        # calculated:
        seven_day_stats = TimespanBinder(TimeSpan(week_ts, timespan.stop),
                                         db_lookup,
                                         formatter=self.generator.formatter,
                                         converter=self.generator.converter) # 7

        # Now create a small dictionary with keys 'alltime' and 'seven_day':
        search_list_extension = {'alltime'   : all_stats,
                                 'seven_day' : seven_day_stats}              # 8
        
        # Finally, return our extension as a list:
        return [search_list_extension]                                       # 9
