# Running WeeWX
WeeWX can be run either directly, or as a daemon. When first trying WeeWX, it is best to run it directly because you will be able to see sensor output and diagnostics, as well as log messages. Once everything is working properly, run it as a daemon.

## Running directly
To run WeeWX directly, invoke the main program, `weewxd`. Depending on device permissions, you may
or may not have to use `sudo`.

```shell
weewxd
```

!!! note
    
    If your configuration file is named something other than `weewx.conf`, or if it is in a non-standard place, then you will have to specify it explicitly on the command line. For example:

    ```
    weewxd /some/path/to/weewx.conf
    ```

If your station has a data logger, the program will start by downloading any data stored in your weather station into the archive database. For some stations, such as the Davis Vantage with a couple thousand records, this could take a minute or two.

WeeWX will then start monitoring live sensor data (also referrred to as 'LOOP' data), printing a short version of the received data on standard output, about once every two seconds for a Vantage station, or considerably longer for some other stations.


## Running as a daemon
For unattended operations it is best to have WeeWX run as a daemon, started automatically when the server is rebooted.

If you use a packaged installer, this is done automatically. The installer finishes with a daemon running in the background. 

For a pip install, you will have to do this yourself. See the section [*Run as a daemon*](../../quickstarts/pip/#run-as-a-daemon) in the pip quick start guide.

## Monitoring WeeWX
WeeWX logs many events to the system log. On Debian systems, this is `/var/log/syslog`, on SuSE, `/var/log/messages`. Your system may use yet another place. When troubleshooting the system, be sure to check it!

To watch the log as it is generated, use the tail command with the `-f` option:

```
tail -f /var/log/syslog
```

Set the [`debug`](../weewx-config-file/general/#debug) option in `weewx.conf` to generate many more checks and output more information. This can be useful for diagnosing problems and debugging.

```
debug = 1
```