# Troubleshooting

If you are having problems, first look at the hardware, software, and
meteorological problems pages. You might be experiencing a problem that
someone else has already solved.

[Hardware problems](hardware.md)<br/>
[Software problems](software.md)<br/>
[Meteorological problems](meteo.md)

Read the [Frequently Asked Questions](https://github.com/weewx/weewx/wiki/WeeWX-Frequently-Asked-Questions) (FAQ).  Search the
[weewx-user group](https://groups.google.com/g/weewx-user), especially
if you are using a driver or skin that is not part of the WeeWX core.

If you still have problems, here are a few things to try on your system:

1. Look at the [log file](../monitoring.md#log-messages). We
are always happy to take questions, but the first thing someone will ask is,
"What did you find in the log file?"

2. Run `weewxd` directly, rather than as a daemon. Generally, WeeWX will catch
and log any unrecoverable exceptions, but if you are getting strange results,
it is worth running directly and looking for any clues.

3. Set the option `debug = 1` in `weewx.conf`. This will put much more
information in the log file, which can be very useful for troubleshooting
and debugging!

If you are _still_ stuck, post your problem to the
[weewx-user group](https://groups.google.com/g/weewx-user). The Wiki has some
guidelines on [how to do an effective post](https://github.com/weewx/weewx/wiki/Help!-Posting-to-weewx-user).
