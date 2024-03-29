xstats
======

WeeWX extension that provides extended statistics for reports

Copyright 2014-2024 Matthew Wall

This search list extension offers extra tags:

  'alltime':    All time statistics.
                For example, "what is the all-time high temperature?"
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

Installation instructions using the installer (recommended)
-----------------------------------------------------------

1) Install the extension.

    For pip installs:

        weectl extension install ~/weewx-data/examples/xstats

    For package installs

        sudo weectl extension install /usr/share/doc/weewx/examples/xstats


2) Restart WeeWX

        sudo systemctl restart weewx


This will result in a report called xstats that illustrates the use of the
extended statistics.


Manual installation instructions
--------------------------------

1) Copy the file `xstats.py` to the WeeWX `user` directory.

    For pip installs:

        cd ~/weewx-data/examples/xstats
        cp bin/user/xstats.py ~/etc/weewx-data/bin/user

    For package installs:

        cd /usr/share/doc/weewx/examples/xstats
        sudo cp bin/user/xstats.py /usr/share/weewx/user

2) Copy the `xstats` demonstration skin to the `skins` directory.

    For pip installs:

        cd ~/weewx-data/examples/xstats
        cp skins/xsstats ~/weewx-data/skins/

    For package installs:

        cd /usr/share/doc/weewx/examples/xstats
        sudo cp skins/xstats/ /etc/weewx/skins/


3) In the WeeWX configuration file, arrange to use the demonstration skin `xstats`.

        [StdReport]
            ...
            [[XStats]]
                skin = xstats
                HTML_ROOT = xstats

3) Restart WeeWX

        sudo systemctl restart weewx
