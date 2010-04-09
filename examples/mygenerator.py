#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#

"""Example of how to extend a generator.

This generator offers tag 'alltime' that makes all-time statistics available,
such as the all-time max temperature.

To use it, in the skin's generator_list, replace weewx.filegenerator.FileGenerator
with examples.mygenerator.MyFileGenerator.

You can then use tags such as $alltime.outTemp.max for the all-time max temperature.
"""

from weewx.filegenerator import FileGenerator
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan

class MyFileGenerator(FileGenerator):                    # 1
  
    def getToDateSearchList(self, currentRec, stop_ts):  # 2

        # Get a TimeSpan object that represents all time up to the stop time:
        all_time = TimeSpan(self.start_ts, stop_ts)      # 3

        # Get a TimeSpanStats object :
        all_stats = TimeSpanStats(self.statsdb,
                                  all_time,
                                  unit_info=self.unit_info) # 4

        # Get the superclass's search list:       
        search_list = FileGenerator.getToDateSearchList(self, currentRec, stop_ts) #5

        # Now tack on my addition as a small dictionary with key 'alltime':
        search_list += [ {'alltime' : all_stats} ]       # 6
        
        return search_list

