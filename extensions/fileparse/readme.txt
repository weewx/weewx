fileparse - simple driver that reads data from a file
Copyright 2014 Matthew Wall

This driver illustrates how to package a driver so it can be installed by the
weewx extension installer.


Installation instructions:

cd /home/weewx
setup.py --extension --install extensions/fileparse


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
