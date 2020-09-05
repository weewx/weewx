fileparse - simple driver that reads data from a file
Copyright 2014 Matthew Wall

This example illustrates how to implement a driver and package it so that it
can be installed by the extension installer.  The fileparse driver reads data
from a file of name=value pairs.


Installation instructions

1) install the extension

wee_extension --install=/home/weewx/examples/fileparse

2) select the driver

wee_config --reconfigure

3) restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


Manual installation instructions

1) copy the fileparse driver to the WeeWX user directory

cp /home/weewx/examples/fileparse/bin/fileparse.py /home/weewx/bin/user

2) add a new [FileParse] stanza to the WeeWX configuration file

[FileParse]
    poll_interval = 10
    path = /var/tmp/datafile
    driver = user.fileparse

3) If the variables in the file have names different from those in the database
schema, then add a mapping section called label_map.  This will map the
variables in the file to variables in the database columns.  For example:

[FileParse]

    ... (as before)

    [[label_map]]
        temp = outTemp
        humi = outHumidity
        in_temp = inTemp
        in_humid = inHumidity

4) in the WeeWX configuration file, modify the station_type setting to use the
fileparse driver

[Station]
    ...
    station_type = FileParse

5) restart WeeWX

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
