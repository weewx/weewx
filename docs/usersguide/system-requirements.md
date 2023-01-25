# System requirements

## Python
Python 3.7 or later is required. WeeWX V5.x will not run on Python 2.

## Station hardware
WeeWX includes support for many types of weather stations. In addition to hardware support, WeeWX comes with a software simulator, useful for testing and evaluation.

The [driver compatibility table](../hardware.htm#driver_status) in the hardware guide has a detailed list of the manufacturers and models supported by the drivers that come with WeeWX. If you do not see your hardware in this table, check the list of [supported hardware](https://weewx.com/hardware.html); the pictures may help you identify the manufacturer and/or model. Compatibility for some hardware is provided by 3rd party drivers, available at the [Wiki](https://github.com/weewx/weewx/wiki). Finally, check the hardware comparison to see if your hardware is known but not yet supported.

If you still cannot find your hardware, post to the [User's Group](https://groups.google.com/g/weewx-user) for help.


## Computer hardware
WeeWX is written in Python, so it has the overhead associated with that language. Nevertheless, it is "fast enough" on just about any hardware. It has been run on everything from an early MacBook to a router!

I run WeeWX on a vintage 32-bit Fit-PC with a 500 MHz AMD Geode processor and 512 MB of memory. Configured this way, it consumes about 5% of the CPU, 150 MB of virtual memory, and 50 MB of real memory.

WeeWX also runs great on a Raspberry Pi, although report generation will take longer. For example, the 12 "To Date" templates of the "Standard" report take about 5.1 seconds on a RPi B+, compared to 3.0 seconds on the Fit-PC, and 0.3 seconds on a NUC with a 4th gen i5 processor.


## Time
You should run some sort of time synchronization daemon to ensure that your computer has the correct time. Doing so will greatly reduce errors, especially if you send data to services such as the Weather Underground. Systemd systems can use systemd-timesyncd, other systems can use NTP. See the Wiki article [*Time services*](https://github.com/weewx/weewx/wiki/Time-services).

The time on some stations is automatically synchronized with the WeeWX server nominally every four hours. The synchronization frequency can be adjusted in the WeeWX configuration.
