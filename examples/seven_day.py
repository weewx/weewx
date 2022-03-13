#    Copyright (c) 2009-2021 Tom Keffer <tkeffer@gmail.com>
#    See the file LICENSE.txt for your rights.

"""Implementation of a $seven_day search list extension.

*******************************************************************************

This search list extension offers an extra tag:

    'seven_day': Statistics for the last seven days.
                 That is, since midnight seven days ago.

*******************************************************************************

To use this search list extension:

1) Copy this file to the user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

2) Modify the option search_list in the skin.conf configuration file, adding
the name of this extension.  When you're done, it will look something like
this:

[CheetahGenerator]
    search_list_extensions = user.seven_day.SevenDay

You can then use tags such as $seven_day.rain.sum for the total rainfall in the last
seven days.

*******************************************************************************
"""
import datetime
import time

from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan

class SevenDay(SearchList):                                                  # 1

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

        # Create a TimespanBinder object for the last seven days. First, calculate
        # the time at midnight, seven days ago. The variable week_dt will be an instance of
        # datetime.date.
        week_dt = datetime.date.fromtimestamp(timespan.stop) \
                  - datetime.timedelta(weeks=1)                              # 4
        # Convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())                           # 5
        # Form a TimespanBinder object, using the time span we just
        # calculated:
        seven_day_stats = TimespanBinder(TimeSpan(week_ts, timespan.stop),
                                         db_lookup,
                                         context='week',
                                         formatter=self.generator.formatter,
                                         converter=self.generator.converter,
                                         skin_dict=self.generator.skin_dict) # 6

        # Now create a small dictionary with the key 'seven_day':
        search_list_extension = {'seven_day' : seven_day_stats}              # 7
        
        # Finally, return our extension as a list:
        return [search_list_extension]                                       # 8
