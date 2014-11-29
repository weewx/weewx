fileparse - simple driver that reads data from a file
Copyright 2014 Matthew Wall

This example illustrates how to implement a driver and package it so that it
can be installed by the extension installer.  The fileparse driver reads data
from a file of name=value pairs.


Installation instructions:

1) run the installer:

setup.py install --extension extensions/fileparse

2) start weewx:

sudo /etc/init.d/weewx start


Manual installation instructions:

1) copy files to the weewx user directory:

cp bin/user/fileparse.py /home/weewx/bin/user

2) modify weewx.conf:

[Station]
    station_type = FileParse

[FileParse]
    poll_interval = 60         # number of seconds
    path = /var/tmp/datafile   # location of data file
    driver = user.fileparse

3) start weewx

sudo /etc/init.d/weewx start
