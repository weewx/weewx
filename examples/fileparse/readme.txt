fileparse - simple driver that reads data from a file
Copyright 2014 Matthew Wall

This example illustrates how to implement a driver and package it so that it
can be installed by the extension installer.  The fileparse driver reads data
from a file of name=value pairs.


Installation instructions:

1) install the extension

wee_extension --install extensions/fileparse

2) select the driver

wee_config --reconfigure

3) start weewx:

sudo /etc/init.d/weewx start
