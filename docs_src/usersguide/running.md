# Running WeeWX

WeeWX can be run either directly, or as a daemon. When first trying WeeWX, it
is best to run it directly because you will be able to see sensor output and
diagnostics, as well as log messages. Once everything is working properly, run
it as a daemon.

## Running directly

To run WeeWX directly, invoke the main program, `weewxd`.  To stop it, type
`ctrl-c` (press and hold the `control` key then hit the `c` key).

```shell
weewxd
```

!!! note
    Depending on device permissions, you may need root permissions to
    communicate with the station hardware.  If this is the case, use `sudo`:
    ```shell
    sudo weewxd
    ```

!!! note
    
    If your configuration file is named something other than `weewx.conf`, or
    if it is in a non-standard place, then you will have to specify it
    explicitly on the command line. For example:

    ```
    weewxd --config=/some/path/to/weewx.conf
    ```

If your weather station has a data logger, the program will start by
downloading any data stored in the logger into the archive database. For some
stations, such as the Davis Vantage with a couple of thousand records, this
could take a minute or two.

WeeWX will then start monitoring live sensor data (also referred to as 'LOOP'
data), printing a short version of the received data on standard output, about
once every two seconds for a Vantage station, or considerably longer for some
other stations.


## Running as a daemon

For unattended operations it is best to have WeeWX run as a daemon, so that
it is started automatically when the computer starts up.

If you installed WeeWX from DEB or RPM package, the daemon configuration is
done automatically; the installer finishes with WeeWX running in the
background.

For a pip install, you will have to configure the daemon yourself. See the
section [_Run as a daemon_](../quickstarts/pip.md#run-as-a-daemon) in the pip
quick start guide.

After the daemon is configured, use the tools appropriate to your operating
system to start and stop WeeWX.

=== "systemd"

    ```{ .shell .copy }
    # For Linux systems that use systemd, e.g., Debian, Redhat, SUSE
    sudo systemctl start weewx
    sudo systemctl stop weewx
    ```

=== "SysV"

    ```{ .shell .copy }
    # For Linux systems that use SysV init, e.g., Slackware, Devuan, Puppy
    sudo /etc/init.d/weewx start
    sudo /etc/init.d/weewx stop
    ```

=== "BSD"

    ```{ .shell .copy }
    # For BSD systems, e.g., FreeBSD, OpenBSD
    sudo service weewx start
    sudo service weewx stop
    ```

=== "macOS"

    ```{ .shell .copy }
    # For macOS systems.
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```

When `weewxd` runs in the background, you will not see sensor data or any other
indication that it is running.  However, there are several approaches you can
take to see what's happening:

- Use your system's [status tools](monitoring.md#status) to monitor its state;
- Look at any generated [reports](monitoring.md#reports); and
- Look at the [logs](monitoring.md#log-messages).
