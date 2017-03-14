xstats - weewx extension that provides extended statistics for reports
Copyright 2014 Matthew Wall

This search list extension offers extra tags:

  'alltime':    All time statistics.
                For example, "what is the all time high temperature?"
                $alltime.outTemp.max

  'seven_day':  Statistics for the last seven days, i.e., since midnight
                seven days ago.  For example, "what is the maximum wind
                speed in the last seven days?"
                $seven_day.wind.max

  'thirty_day': Statistics for the last thirty days, i.e., since midnight
                thirty days ago.  For example, "what is the maximum wind
                speed in the last thirty days?"
                $thirty_day.wind.max


Installation instructions:

1) run the installer:

setup.py install --extension extensions/xstats

2) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start

This will result in a report called xstats that illustrates the use of the
extended statistics.


Manual installation instructions:

1) copy files to the weewx user directory:

cp bin/user/xstats.py /home/weewx/bin/user

2) in weewx.conf, modify the report section in which you would like to use the
   extended statistics.  for example, for the StandardReport:

[StdReport]
    [[StandardReport]]
        ...
        [[[CheetahGenerator]]]
            search_list_extensions = user.xstats.ExtendedStatistics

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
