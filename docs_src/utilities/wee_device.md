# wee_device

The utility `wee_device` is used to configure hardware settings, such as rain
bucket size, station archive interval, altitude, EEPROM constants, <i>etc.</i>,
on your station. In order to do its job, it depends on optional code being
present in the hardware driver. Because not all drivers have this code, it may
not work for your specific device. If it does not, you will have to consult
your manufacturer's instructions for how to set these things through your
console or other means.

`wee_device` uses the option `station_type` in `weewx.conf` to determine what
device you are using and what options to display. Make sure it is set correctly
before attempting to use this utility.

Because `wee_device` uses hardware-specific code, its options are different for
every station type. You should run it with `--help` to see how to use it for
your specific station:

```
wee_device --help
```

The utility requires a WeeWX configuration file. If no file is specified, it
will look for a file called `weewx.conf` in the standard location. If your
configuration file is in a non-standard location, specify the path to the
configuration file as the first argument. For example,

```
wee_device /path/to/weewx.conf --help
```

For details about the options available for each type of hardware, see the
appropriate hardware section:


<li><a href="../hardware.htm#acurite_notes">AcuRite</a></li>
<li><a href="../hardware.htm#cc3000_notes">CC3000</a></li>
<li><a href="../hardware.htm#fousb_notes">FineOffsetUSB</a></li>
<li><a href="../hardware.htm#te923_notes">TE923</a></li>
<li><a href="../hardware.htm#ultimeter_notes">Ultimeter</a></li>
<li><a href="../hardware.htm#vantage_notes">Vantage</a></li>
<li><a href="../hardware.htm#wmr100_notes">WMR100</a></li>
<li><a href="../hardware.htm#wmr300_notes">WMR300</a></li>
<li><a href="../hardware.htm#wmr9x8_notes">WMR9x8</a></li>
<li><a href="../hardware.htm#ws1_notes">WS1</a></li>
<li><a href="../hardware.htm#ws23xx_notes">WS23xx</a></li>
<li><a href="../hardware.htm#ws28xx_notes">WS28xx</a></li>
