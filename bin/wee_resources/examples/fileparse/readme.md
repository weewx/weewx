fileparse - simple driver that reads data from a file
==========

Copyright 2014-2023 Matthew Wall

This example illustrates how to implement a driver and package it so that it
can be installed by the extension installer.  The fileparse driver reads data
from a file of name=value pairs.


Installation instructions using the installer (recommended)
-----------------------------------------------------------

1) Install the extension.

    For pip installs:

        weectl extension install ~/weewx-data/examples/fileparse

    For package installs

        sudo weectl extension install /usr/share/doc/weewx/examples/fileparse

2) Select the driver.

    For pip installs:

        weectl station reconfigure 

    For package installs:

        sudo weectl station reconfigure

3) Restart WeeWX

        sudo systemctl restart weewx


Manual installation instructions
--------------------------------

1) Copy the fileparse driver to the WeeWX user directory.

    For pip installs:

        cd ~/weewx-data/examples/fileparse
        cp bin/user/fileparse.py ~/etc/weewx-data/bin/user

    For package installs:

        cd /usr/share/doc/weewx/examples/fileparse
        sudo cp bin/user/fileparse.py /usr/share/weewx/user

2) Add a new `[FileParse]` stanza to the WeeWX configuration file

       [FileParse]
           poll_interval = 10
           path = /var/tmp/datafile
           driver = user.fileparse

3) If the variables in the file have names different from those in the database
schema, then add a mapping section called `label_map`.  This will map the
variables in the file to variables in the database columns.  For example:

       [FileParse]
    
           ... (as before)
    
           [[label_map]]
               temp = outTemp
               humi = outHumidity
               in_temp = inTemp
               in_humid = inHumidity

4) In the WeeWX configuration file, modify the `station_type` setting to use the
fileparse driver

       [Station]
           ...
           station_type = FileParse

5) Restart WeeWX

        sudo systemctl restart weewx
