xstats - weeWX extension that provides extended statistics for reports
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


Installation instructions

1) install the extension

wee_extension --install=/home/weewx/examples/xstats

2) restart weeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start

This will result in a report called xstats that illustrates the use of the
extended statistics.


Manual installation instructions

1) copy files to the weeWX user directory

cp bin/user/xstats.py /home/weewx/bin/user

2) in the weeWX configuration file, modify the report section in which you 
would like to use the extended statistics. For example, for the StandardReport

[StdReport]
    [[StandardReport]]
        ...
        [[[CheetahGenerator]]]
            search_list_extensions = user.xstats.ExtendedStatistics

3) restart weeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
