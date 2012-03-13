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

This generator offers tag 'alltime' that makes all-time statistics available,
such as the all-time max temperature.

To use it, in the skin's generator_list, replace weewx.filegenerator.FileGenerator
with examples.mygenerator.MyFileGenerator.

You can then use tags such as $alltime.outTemp.max for the all-time max temperature.
"""

from weewx.filegenerator import FileGenerator
from weewx.stats import TimeSpanStats

class MyFileGenerator(FileGenerator):                            # 1
  
    def getToDateSearchList(self, archivedb, statsdb, timespan): # 2

        # Get a TimeSpanStats object :
        all_stats = TimeSpanStats(timespan,
                                  statsdb,
                                  formatter=self.formatter,
                                  converter=self.converter)      # 3

        # Get the superclass's search list:       
        search_list = FileGenerator.getToDateSearchList(self, archivedb, statsdb, timespan) # 4

        # Now tack on my addition as a small dictionary with key 'alltime':
        search_list += [ {'alltime' : all_stats} ]               # 5
        
        return search_list

