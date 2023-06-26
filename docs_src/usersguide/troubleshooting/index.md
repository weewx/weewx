# Troubleshooting

These are some common problems users encounter when installing and running WeeWX.

[Hardware Problems](hardware)<br/>
[Software Problems](software)<br/>
[Meteorological Problems](meteo)

If you have problems, here are a few things to try:

1. Look at the [log file](../../usersguide/running-weewx#monitoring-weewx). We are always happy to take questions, but the first thing someone will ask is, "What did you find in the log file?"

2. Run `weewxd` directly, rather than as a daemon. Generally, WeeWX will catch and log any unrecoverable exceptions, but if you are getting strange results, it is worth running directly and looking for any clues.

3. Set the option `debug = 1` in `weewx.conf`. This will put much more information in the log file, which can be very useful for troubleshooting and debugging!

4. If you are still stuck, post your problem to the [weewx-user group](https://groups.google.com/g/weewx-user). The Wiki has some guidelines on [how to do an effective post](https://github.com/weewx/weewx/wiki/Help!-Posting-to-weewx-user).
