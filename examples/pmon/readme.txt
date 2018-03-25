pmon - Process Monitor
Copyright 2014 Matthew Wall

This example illustrates how to implement a service and package it so that it
can be installed by the extension installer.  The pmon service collects memory
usage information about a single process then saves it in its own database.
Data are then displayed using standard weewx reporting and plotting utilities.


Installation instructions:

1) install the extension:

wee_extension --install=/home/weewx/examples/pmon

2) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


This will result in a skin called pmon with a single web page that illustrates
how to use the monitoring data.  See comments in pmon.py for customization
options.


Manual installation instructions:

1) copy the pmon service file to the weewx user directory:

cp /home/weewx/examples/pmon/bin/pmon.py /home/weewx/bin/user

2) copy files to the weewx skins directory:

cp -rp skins/pmon /home/weewx/skins

3) add a new [ProcessMonitor] stanza in weewx.conf:

[ProcessMonitor]
    data_binding = pmon_binding
    process = weewxd

4) in weewx.conf, add a binding to [DataBindings]:

[DataBindings]
    ...
    [[pmon_binding]]
        database = pmon_sqlite
        table_name = archive
        manager = weewx.manager.DaySummaryManager
        schema = user.pmon.schema

5) in weewx.conf, add a database to [Databases]:

[Databases]
    ...
    [[pmon_sqlite]]
        database_name = pmon.sdb
        driver = weedb.sqlite

6) in weewx.conf, add a report to [StdReport]:

[StdReport]
    ...
    [[pmon]]
        skin = pmon
        HTML_ROOT = pmon

7) in weewx.conf, add an entry for pmon to the end of the process_services 
option under [Engine] [[Services]]:

[Engine]
    [[Services]]
        process_services = ..., user.pmon.ProcessMonitor

8) restart weewx:

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
