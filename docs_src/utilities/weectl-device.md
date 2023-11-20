# weectl device

The `weectl` subcommand `device` is used to configure hardware settings, such as
rain bucket size, station archive interval, altitude, EEPROM constants, *etc.*,
on your station. In order to do its job, it depends on optional code being
present in the hardware driver. Because not all drivers have this code, it may
not work for your specific device. If it does not, you will have to consult your
manufacturer's instructions for how to set these things through your console or
other means.

`weectl device` uses the option `station_type` in `weewx.conf` to determine what
device you are using and what options to display. Make sure it is set correctly
before attempting to use this utility.

Because `weectl device` uses hardware-specific code, its options are different
for every station type. You should run it with `--help` to see how to use it for
your specific station:

    weectl device --help

The utility requires a WeeWX configuration file. If no file is specified, it
will look for a file called `weewx.conf` in the standard location. If your
configuration file is in a non-standard location, specify the path to the
configuration file either as the first argument, or by using the `--config`
option. For example,

    weectl device /path/to/weewx.conf --help

or

    weectl device --config=/path/to/weewx.conf --help

For details about the options available for each type of hardware, see the
appropriate hardware section:

* [AcuRite](../hardware/acurite.md)
* [CC3000](../hardware/cc3000.md)
* [FineOffset](../hardware/fousb.md)
* [TE923](../hardware/te923.md)
* [Ultimeter](../hardware/ultimeter.md)
* [Vantage](../hardware/vantage.md)
* [WMR100](../hardware/wmr100.md)
* [WMR300](../hardware/wmr300.md)
* [WMR9x8](../hardware/wmr9x8.md)
* [WS1](../hardware/ws1.md)
* [WS23xx](../hardware/ws23xx.md)
* [WS28xx](../hardware/ws28xx.md)
