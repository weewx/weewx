xstats - weewx extension that provides extended statistics in a report
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

cd /home/weewx
setup.py --extension --install extensions/xstats


Manual installation instructions:

1) copy files to the weewx user directory:

cp bin/user/xstats.py /home/weewx/bin/user

2) modify the appropriate report section in weewx.conf:

[StdReport]
    [[StandardReport]]
        [[[CheetahGenerator]]]
            search_list_extensions = user.xstats.ExtendedStatistics

3) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
