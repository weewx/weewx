# Running WeeWX
WeeWX can be run either directly, or as a daemon. When first trying WeeWX, it is best to run it directly because you will be able to see sensor output and diagnostics, as well as log messages. Once everything is working properly, run it as a daemon.

## Running directly
To run WeeWX directly, invoke the main program, **weewxd**:

```
sudo weewxd
```

!!! note
    
    If your configuration file is named something other than weewx.conf, or if it is in a non-standard place, then you will have to specify it explicitly on the command line. For example:

    ```
    sudo weewxd /some/path/to/weewx.conf
    ```

If your station has a data logger, the program will start by downloading any data stored in your weather station into the archive database. For some stations, such as the Davis Vantage with a couple thousand records, this could take a minute or two.

WeeWX will then start monitoring live sensor data (also referrred to as 'LOOP' data), printing a short version of the received data on standard output, about once every two seconds for a Vantage station, or considerably longer for some other stations.


## Running as a daemon
For unattended operations it is best to have WeeWX run as a daemon, started automatically when the server is rebooted.

If you use a packaged install from a DEB or RPM distribution, this is done automatically. You can ignore this section.

Start by selecting the appropriate run script. They can be found in the source or installation under **util/init.d/**.

| OS | Init Script Location |
| -- | -------------------- |
| Debian/Ubuntu/Mint: |	util/init.d/weewx.debian |
| Redhat/CentOS/Mint: |	util/init.d/weewx.redhat |
| SuSE: | util/init.d/weewx.suse |

Check the chosen script to make sure the variable **WEEWX_ROOT** has been set to the proper root directory for your WeeWX installation (it should have been set to the correct value automatically by the install process, but it is worth checking).

Copy it to the proper location for your system. Follow these commands (based on your O/S) to make the script executable with symbolic links in the run level directories:

=== "Debian/Ubuntu/Mint"
    ```
    cp util/init.d/weewx.debian /etc/init.d/weewx
    chmod +x /etc/init.d/weewx
    update-rc.d weewx defaults 98
    ```

=== "Redhat/CentOS/Fedora"
    ```
    cp util/init.d/weewx.redhat /etc/rc.d/init.d/weewx
    chmod +x /etc/init.d/rc.d/weewx
    chkconfig weewx on
    ```
=== "SuSE"
    ```
    cp util/init.d/weewx.suse /etc/init.d/weewx
    chmod +x /etc/init.d/weewx
    /usr/lib/lsb/install_initd /etc/init.d/weewx
    ```


WeeWX will now start automatically whenever your system is booted. You can also manually start, stop, and restart the WeeWX daemon:

```
sudo /etc/init.d/weewx start
sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx restart
```

By default, the scripts are designed to have WeeWX run at run levels 2, 3, 4 and 5. Incidentally, a nice tool for setting run levels with Debian (Ubuntu, Mint) systems is [sysv-rc-conf](http://sysv-rc-conf.sourceforge.net/). It uses a curses interface to allow you to change easily which run level any of your daemons runs at. There is a similar tool on SuSE. From the start menu run the YAST Control Center, then look for Systems Services (Runlevel). Pick "Expert" mode to see the run levels.

## Monitoring WeeWX
WeeWX logs many events to the system log. On Debian systems, this is **/var/log/syslog**, on SuSE, **/var/log/messages**. Your system may use yet another place. When troubleshooting the system, be sure to check it!

To watch the log as it is generated, use the tail command with the **-f** option:

```
tail -f /var/log/syslog
```

Set the debug option in **weewx.conf** to generate many more checks and output more information. This can be useful for diagnosing problems and debugging.

```
debug = 1
```