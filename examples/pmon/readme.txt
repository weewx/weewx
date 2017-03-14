pmon - Process Monitor
Copyright 2014 Matthew Wall

This example illustrates how to implement a service and package it so that it
can be installed by the extension installer.  The pmon service collects memory
usage information about a single process then saves it in its own database.
Data are then displayed using standard weewx reporting and plotting utilities.


Installation instructions:

1) run the installer:

wee_extension --install extensions/pmon

2) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


This will result in a skin called pmon with a single web page that illustrates
how to use the monitoring data.  See comments in pmon.py for customization
options.
