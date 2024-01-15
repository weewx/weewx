# User's Guide

This is the complete guide to installing, configuring, and troubleshooting
WeeWX.

## System requirements

### Python

Python 3.6 or later is required. Python 2 will not work.


### Station hardware

WeeWX includes support for many types of weather stations. In addition to
hardware support, WeeWX comes with a software simulator, useful for testing
and evaluation.

The [driver compatibility table](../hardware/drivers.md) in the _Hardware
guide_ has a detailed list of the manufacturers and models supported by the
drivers that come with WeeWX. If you do not see your hardware in this table,
check the list of [supported hardware](https://weewx.com/hardware.html); the
pictures may help you identify the manufacturer and/or model. Compatibility for
some hardware is provided by 3rd party drivers, available at the
[Wiki](https://github.com/weewx/weewx/wiki). Finally, check the [hardware
comparison](https://weewx.com/hwcmp.html) to see if your hardware is known, but
not yet supported.

If you still cannot find your hardware, post to the
[User's Group](https://groups.google.com/g/weewx-user) for help.


### Computer hardware

WeeWX is written in Python, so it has the overhead associated with that
language. Nevertheless, it is "fast enough" on just about any hardware.
It has been run on everything from an early MacBook to a router!

I run WeeWX on a vintage 32-bit Fit-PC with a 500 MHz AMD Geode processor and
512 MB of memory. Configured this way, it consumes about 5% of the CPU, 150 MB
of virtual memory, and 50 MB of real memory.

WeeWX also runs great on a Raspberry Pi, although report generation will take
longer. For example, here are some generation times for the 21 HTML files and 68
images used by the _Seasons_ skin. See the Wiki article [_Benchmarks of file and
image generation_
](https://github.com/weewx/weewx/wiki/Benchmarks-of-file-and-image-generation)
for details.

| Hardware               | Files (21) | Images (68) |
|------------------------|-----------:|------------:|
| Mac Mini, M1 2020      |      0.60s |       1.06s |
| NUC Intel i7, 11th gen |      0.89s |       1.14s |
| RPI 5                  |      1.63s |       2.03s |
| RPi 4                  |      6.24s |       6.39s |
| RPi 3                  |     13.06s |      14.07s |       
| RPi 2 (32-bit)         |     24.27s |      25.95s |
| Rpi Zero W (32-bit)    |     53.97s |      57.79s |


### Time

You should run some sort of time synchronization daemon to ensure that your
computer has the correct time. Doing so will greatly reduce errors, especially
if you send data to services such as the Weather Underground. See the Wiki
article [*Time services*](https://github.com/weewx/weewx/wiki/Time-services).

On stations that support it, the time is automatically synchronized with the
WeeWX server, nominally every four hours. The synchronization frequency can
be adjusted in the WeeWX configuration.
