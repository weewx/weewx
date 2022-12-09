xstats - WeeWX extension that provides extended statistics for reports
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
                
  'last_month': Statistics for last calendar month, this is useful in
                getting statistics such as the maximum/minimum records.
                $last_month.outTemp.max at $last_month.outTemp.maxtime
                $last_month.outTemp.min at $last_month.outTemp.mintime
    
  'last_year':  Statistics for last calendar year, this is useful for
                things like total rainfall for last year.
                $last_year.rain.sum
  
  'last_year_todate': Statistics of last calendar year until this time
                      last year. This is useful for comprisons of rain
                      fall up to this time last year.
                      $last_year_todate.rain.sum

Installation instructions

1) install the extension

wee_extension --install=/home/weewx/examples/xstats

2) Restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start

This will result in a report called xstats that illustrates the use of the
extended statistics.


Manual installation instructions

1) Copy files to the WeeWX user directory. See https://bit.ly/33YHsqX for where your user
directory is located.

cp bin/user/xstats.py /home/weewx/bin/user

2) In the WeeWX configuration file, modify the report section in which you
would like to use the extended statistics. For example, for the StandardReport

[StdReport]
    [[StandardReport]]
        ...
        [[[CheetahGenerator]]]
            search_list_extensions = user.xstats.ExtendedStatistics

3) Restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
