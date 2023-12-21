# Running WeeWX

WeeWX can be run either directly, or as a daemon. When first trying WeeWX, it
is best to run it directly because you will be able to see sensor output and
diagnostics, as well as log messages. Once everything is working properly, run
it as a daemon.

## Running directly

To run WeeWX directly, invoke the main program, `weewxd`.

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
it is started automatically when the computer is rebooted.

If you installed WeeWX from DEB or RPM package, this is done automatically;
the installer finishes with WeeWX running in the background.

For a pip install, you will have to do this yourself. See the section [_Run as
a daemon_](../quickstarts/pip.md#run-as-a-daemon) in the pip quick start guide.

When `weewxd` runs in the background, you will not see sensor data or any
other indication that it is running.  To see what is happening, use your
system's `init` tools, look at the logs, and look at the reports.


## Monitoring WeeWX

Whether you run `weewxd` directly or in the background, `weewxd` emits
messages about its status and generates reports.  The status messages will
help you diagnose problems.

### Status

If WeeWX is running in the background, you can use the system's `init` tools
to check the status.  For example, on systems that use `systemd`, check it
like this:
```{.shell .copy}
systemctl status weewx
```
On systems that use `sysV` init scripts, check it like this:
```{.shell .copy}
/etc/init.d/weewx status
```

### Reports

When it is running properly, WeeWX will generate reports, typically every five
minutes.  The reports are not (re)generated until data have been received and
accumulated, so it could be a few minutes before you see a report or a change
to a report. The location of the reports depends on the operating system and
how WeeWX was installed.

See `HTML_ROOT` in the [*Where to find things*](../where) section.

Depending on the configuration, if WeeWX cannot get data from the sensors,
then it will probably not generate any reports.  So if you do not see reports,
check the log!

### Log messages

In the default configuration, WeeWX logs to the system logging facility.

On traditional systems, the system logging facility puts the WeeWX messages
into a file, along with other messages from the system. The location of the
system log file varies, but it is typically `/var/log/syslog` or
`/var/log/messages`.

You can view the messages using standard tools such as `tail`, `head`, `more`,
`less`, and `grep`.

For example, to see only the messages from `weewxd`:
```{.shell .copy}
grep weewxd /var/log/syslog
```
To see only the latest 40 messages from `weewxd`:
```{.shell .copy}
grep weewxd /var/log/syslog | tail -40
```
To see messages as they come into the log in real time (hit `ctrl-c` to stop):
```{.shell .copy}
tail -f /var/log/syslog
```

Some systems with `systemd` use *only* `systemd-journald` as the system logging
facility.  On these systems, you will have to use the `journalctl` tool to
view messages from WeeWX.

For example, to see only the messages from `weewxd`:
```{.shell .copy}
journalctl -u weewx
```
To see only the latest 40 messages from `weewxd`:
```{.shell .copy}
journalctl --unit weewx --lines 40
```
To see messages as they come into the log in real time:
```{.shell .copy}
journalctl --unit weewx --follow
```

See the wiki article [*How to view the log*](https://github.com/weewx/weewx/wiki/view-logs) for more information, and examples about how to view and configure
system logs.
