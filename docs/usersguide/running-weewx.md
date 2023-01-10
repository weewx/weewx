# Running WeeWX
WeeWX can be run either directly, or as a daemon. When first trying WeeWX, it is best to run it directly because you will be able to see sensor output and diagnostics, as well as log messages. Once everything is working properly, run it as a daemon.

## Running directly
To run WeeWX directly, invoke the main program, `weewxd`. Depending on device permissions, you may
or may not have to use `sudo`.

```shell
weewxd
```

!!! note
    
    If your configuration file is named something other than weewx.conf, or if it is in a non-standard place, then you will have to specify it explicitly on the command line. For example:

    ```
    weewxd /some/path/to/weewx.conf
    ```

If your station has a data logger, the program will start by downloading any data stored in your weather station into the archive database. For some stations, such as the Davis Vantage with a couple thousand records, this could take a minute or two.

WeeWX will then start monitoring live sensor data (also referrred to as 'LOOP' data), printing a short version of the received data on standard output, about once every two seconds for a Vantage station, or considerably longer for some other stations.


## Running as a daemon
For unattended operations it is best to have WeeWX run as a daemon, started automatically when the server is rebooted. The utility `weectl` can set up the necessary files to do this. 

If you use a packaged install from a DEB or RPM distribution, this is done automatically. You can ignore this section.

To have `weectl` to setup the necessary files:

```shell
sudo weectl daemon install
```

WeeWX will now start automatically whenever your system is booted. You can also manually start, stop, and restart the WeeWX daemon:

```shell
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