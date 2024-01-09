# Monitoring WeeWX

Whether you run `weewxd` directly or in the background, `weewxd` emits
messages about its status and generates reports.  The following sections
explain how to check the status of `weewxd`, locate and view the reports
that it generates, and locate and view the log messages that it emits.

## Status

If WeeWX is running in the background, you can use the system's `init` tools
to check the status.  For example, on systems that use `systemd`, check it
like this:
```{.shell .copy}
systemctl status weewx
```
On systems that use `SysV` init scripts, check it like this:
```{.shell .copy}
/etc/init.d/weewx status
```

## Reports

When it is running properly, WeeWX will generate reports, typically every five
minutes.  The reports are not (re)generated until data have been received and
accumulated, so it could be a few minutes before you see a report or a change
to a report. The location of the reports depends on the operating system and
how WeeWX was installed.

See `HTML_ROOT` in the [*Where to find things*](where.md) section.

Depending on the configuration, if WeeWX cannot get data from the sensors,
then it will probably not generate any reports.  So if you do not see reports,
check the log!

## Log messages

In the default configuration, messages from WeeWX go to the system logging
facility.

The following sections show how to view WeeWX log messages on systems that use
`syslog` and `systemd-journald` logging facilities. See the wiki article
[*How to view the log*](https://github.com/weewx/weewx/wiki/view-logs) for more
details.

See the wiki article [*How to configure
logging*](https://github.com/weewx/weewx/wiki/logging) for information and
examples about how to configure WeeWX logging.


### The `syslog` logging facility

On traditional systems, the system logging facility puts the WeeWX messages
into a file, along with other messages from the system. The location of the
system log file varies, but it is typically `/var/log/syslog` or
`/var/log/messages`.

You can view the messages using standard tools such as `tail`, `head`, `more`,
`less`, and `grep`, although the use of `sudo` may be necessary (the system logs
on most modern systems are readable only to administrative users).

For example, to see only the messages from `weewxd`:
```{.shell .copy}
sudo grep weewxd /var/log/syslog
```
To see only the latest 40 messages from `weewxd`:
```{.shell .copy}
sudo grep weewxd /var/log/syslog | tail -40
```
To see messages as they come into the log in real time (hit `ctrl-c` to stop):
```{.shell .copy}
sudo tail -f /var/log/syslog
```

### The `systemd-journald` logging facility

Some systems with `systemd` use *only* `systemd-journald` as the system logging
facility.  On these systems, you will have to use the tool `journalctl` to view
messages from WeeWX. In what follows, depending on your system, you may or may
not need `sudo`.

For example, to see only the messages from `weewxd`:
```{.shell .copy}
sudo journalctl -u weewx
```

To see only the latest 40 messages from `weewxd`:
```{.shell .copy}
sudo journalctl -u weewx --lines 40
```

To see messages as they come into the log in real time:
```{.shell .copy}
sudo journalctl -u weewx -f
```

## Logging on macOS

Unfortunately, with the introduction of macOS Monterey (12.x), the logging
handler
[`SysLogHandler`](https://docs.python.org/3/library/logging.handlers.html#sysloghandler),
which is used by WeeWX, does not work[^1]. Indeed, the only handlers in the
Python [`logging`](https://docs.python.org/3/library/logging.html) facility
that work with macOS 12.x or later are standalone handlers that log to files.

[^1]: See Python issue [#91070](https://github.com/python/cpython/issues/91070).

Fortunately, there is a simple workaround. Put this at the bottom of your
`weewx.conf` configuration file:

```{.ini .copy}
[Logging]

    [[root]]
        handlers = timed_rotate,

    [[handlers]]
        [[[timed_rotate]]]
            level = DEBUG
            formatter = verbose
            class = logging.handlers.TimedRotatingFileHandler
            filename = log/{process_name}.log
            when = midnight
            backupCount = 7
```

This makes messages from WeeWX go to the file `~/weewx-data/log/weewxd.log`
instead of the system logger.

For an explanation of what all these lines mean, see the wiki article on
[WeeWX logging](https://github.com/weewx/weewx/wiki/WeeWX-v4-and-logging).
