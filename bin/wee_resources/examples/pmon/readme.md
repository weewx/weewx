pmon - Process Monitor
======================

Copyright 2014-2023 Matthew Wall

This example illustrates how to implement a service and package it so that it
can be installed by the extension installer.  The pmon service collects memory
usage information about a single process then saves it in its own database.
Data are then displayed using standard WeeWX reporting and plotting utilities.


Installation instructions using the installer (recommended)
-----------------------------------------------------------

1) Install the extension.

    For pip installs:

        weectl extension install ~/weewx-data/examples/pmon

    For package installs

        sudo weectl extension install /usr/share/doc/weewx/examples/pmon


2) Restart WeeWX

        sudo systemctl restart weewx


This will result in a skin called `pmon` with a single web page that illustrates
how to use the monitoring data.  See comments in pmon.py for customization
options.


Manual installation instructions
--------------------------------

1) Copy the pmon service file to the WeeWX user directory.

    For pip installs:

        cd ~/weewx-data/examples/pmon
        cp bin/user/pmon.py ~/etc/weewx-data/bin/user

    For package installs:

        cd /usr/share/doc/weewx/examples/pmon
        sudo cp bin/user/pmon.py /usr/share/weewx/user


2) Copy the pmon skin to the WeeWX skins directory. 

    For pip installs:

        cd ~/weewx-data/examples/pmon
        cp skins/pmon ~/weewx-data/skins/

    For package installs:

        cd /usr/share/doc/weewx/examples/pmon
        sudo cp skins/pmon/ /etc/weewx/skins/


3) In the WeeWX configuration file, add a new `[ProcessMonitor]` stanza

        [ProcessMonitor]
            data_binding = pmon_binding
            process = weewxd

4) In the WeeWX configuration file, add a data binding

       [DataBindings]
           ...
           [[pmon_binding]]
               database = pmon_sqlite
               table_name = archive
               manager = weewx.manager.Manager
               schema = user.pmon.schema

5) In the WeeWX configuration file, add a database

       [Databases]
           ...
           [[pmon_sqlite]]
               database_name = pmon.sdb
               driver = weedb.sqlite

6) In the WeeWX configuration file, add a report

       [StdReport]
           ...
           [[pmon]]
               skin = pmon
               HTML_ROOT = pmon

7) In the WeeWX configuration file, add the pmon service

       [Engine]
           [[Services]]
               process_services = ..., user.pmon.ProcessMonitor

8) Restart WeeWX

        sudo systemctl restart weewx