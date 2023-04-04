# TroubleShooting Guide

[Hardware Problems](#hardware-problems)<br/>
[Software Problems](#software-problems)<br/>
[Meteorological Problems](#meteorological-problems)

This guide lists some common problems installing and running WeeWX. 

!!! Note
    If you are stuck, be sure to set the option `debug = 1` in `weewx.conf`. This will put much more information in the log file, which can be very useful for troubleshooting and debugging!

Look at the [log file](../../usersguide/running-weewx#monitoring-weewx). We are always happy to take questions, but the first thing someone will ask is, "Did you look at the log file?"

```shell
sudo tail -f /var/log/syslog
```

Run `weewxd` directly from the command line, rather than as a daemon. Generally, WeeWX will catch and log any unrecoverable exceptions, but if you are getting strange results, it is worth running directly from the command line and looking for any clues.

```shell
sudo weewxd weewx.conf
```

If you are still stuck, post your problem to the [weewx-user group](https://groups.google.com/g/weewx-user). The Wiki has some guidelines on [how to do an effective post](https://github.com/weewx/weewx/wiki/Help!-Posting-to-weewx-user).


## Hardware problems

### Davis stations
For Davis-specific tips, see the Wiki article [Troubleshooting Davis stations](https://github.com/weewx/weewx/wiki/Troubleshooting-the-Davis-Vantage-station)

### Tips on making a system reliable
If you are having problems keeping your weather station up for long periods of time, here are some tips, in decreasing order of importance:

* Run on dedicated hardware. If you are using the server for other tasks, particularly as your desktop machine, you will have reliability problems. If you are using it as a print or network server, you will probably be OK.
* Run headless. Modern graphical systems are extremely complex. As new features are added, test suites do not always catch up. Your system will be much more reliable if you run it without a windowing system.
* Use an Uninterruptible Power Supply (UPS). The vast majority of power glitches are very short-lived &mdash; just a second or two &mdash; so you do not need a big one. The 425VA unit I use to protect my fit-PC cost $55 at Best Buy.
* If you buy a Davis VantagePro and your computer has an old-fashioned serial port, get the VantagePro with a serial connection, not a USB connection. See the Wiki article on [Davis cp2101 converter problems](https://github.com/weewx/weewx/wiki/Troubleshooting-the-Davis-Vantage-station#davis-cp2101-converter-problems) for details.
* If you do use a USB connection, put a ferrite coil on each end of the cable to your console. If you have enough length and the ferrite coil is big enough, make a loop so it goes through the coil twice. See the picture below:


<figure markdown>
  ![Ferrite Coils](/images/ferrites.jpg){ width="300" }
  <figcaption>Cable connection looped through a ferrite coil
Ferrite coils on a Davis Envoy. There are two coils, one on the USB connection (top wire) and one on the power supply. Both have loops.</figcaption>
</figure>


### Raspberry Pi

WeeWX runs very well on the Raspberry Pi, from the original Model A and Model B, to the latest incarnations. However, the Pi does have some quirks, including issues with USB power and lack of a clock.

See the [Wiki](https://github.com/weewx/weewx/wiki) for up-to-date information on [Running WeeWX on a Raspberry Pi](https://github.com/weewx/weewx/wiki/Raspberry%20Pi).

### Fine Offset USB lockups

The Fine Offset series weather stations and their derivatives are a fine value and can be made to work reasonably reliably, but they have one problem that is difficult to work around: the USB can unexpectantly lock up, making it impossible to communicate with the console. The symptom in the log will look something like this:

```
Jun 7 21:50:33 localhost weewx[2460]: fousb: get archive interval failed attempt 1 of 3: could not detach kernel driver from interface 0: No data available
```

The exact error may vary, but the thing to look for is the **"could not detach kernel driver"** message. Unfortunately, we have not found a software cure for this. Instead, you must power cycle the unit. Remove the batteries and unplug the USB, then put it back together. No need to restart WeeWX.

More details about [Fine Offset lockups](https://github.com/weewx/weewx/wiki/FineOffset%20USB%20lockup) can be found in the [Wiki](https://github.com/weewx/weewx/wiki).


### Archive interval

Most hardware with data-logging includes a parameter to specify the archive interval used by the logger. If the hardware and driver support it, WeeWX will use this interval as the archive_interval. If not, WeeWX will fall back to using option `archive_interval specified in [[StdArchive]](/usersguide/weewx-config-file/stdarchive). The default fallback value is 300 seconds (5 minutes).

If the hardware archive interval is large, it will take a long time before anything shows up in the WeeWX reports. For example, WS23xx stations ship with an archive interval of 60 minutes, and Fine Offset stations ship with an archive interval of 30 minutes. If you run WeeWX with a WS23xx station in its factory default configuration, it will take 60 minutes before the first data point shows up, then another 60 minutes until the next one, and so on.

Since reports are generated when a new archive record arrives, a large archive interval means that reports will be generated infrequently.

If you want data and reports closer to real-time, use the [wee_device](..//../utilities/utilities.htm#wee_device_utility) utility to change the interval.


## Software problems

This section covers some common software configuration problems.

### Nothing in the log file
As it is running, WeeWX periodically sends status information, failures, and other things to your system's logging facility. They typically look something like this (the first line is not actually part of the log):

``` log
 DATE    TIME       HOST    weewx[PID]  LEVL MESSAGE
Feb  8 04:25:16 hummingbird weewx[6932] INFO weewx.manager: Added record 2020-02-08 04:25:00 PST (1581164700) to database 'weewx.sdb'
Feb  8 04:25:16 hummingbird weewx[6932] INFO weewx.manager: Added record 2020-02-08 04:25:00 PST (1581164700) to daily summary in 'weewx.sdb'
Feb  8 04:25:17 hummingbird weewx[6932] INFO weewx.restx: PWSWeather: Published record 2020-02-08 04:25:00 PST (1581164700)
Feb  8 04:25:17 hummingbird weewx[6932] INFO weewx.restx: Wunderground-PWS: Published record 2020-02-08 04:25:00 PST (1581164700)
Feb  8 04:25:17 hummingbird weewx[6932] INFO weewx.restx: Windy: Published record 2020-02-08 04:25:00 PST (1581164700)
Feb  8 04:25:17 hummingbird weewx[6932] ERROR weewx.restx: WOW: Failed to publish record 2020-02-08 04:25:00 PST (1581164700): Failed upload after 3 tries
```

The location of this logging file varies from system to system, but it is typically in `/var/log/syslog`, or something similar.

However, some systems default to saving only warning or critical information, so **INFO** messages from WeeWX may not appear. If this happens to you, check your system logging configuration. On Debian systems, look in `/etc/rsyslog.conf`. On Redhat systems, look in `/etc/syslog.conf`.


### ConfigObj errors

These are errors in the configuration file. Two are very common. Incidentally, these errors are far easier to diagnose when WeeWX is run directly from the command line than when it is run as a daemon.

#### `configobj.DuplicateError` exception

This error is caused by using an identifier more than once in the configuration file. For example, you may have inadvertently listed your FTP server twice:

```ini
[Reports]
    [[FTP]]
        ... (details elided)
        user = fred
        server = ftp.myhost.com
        password = mypassword
        server = ftp.myhost.com      # OOPS! Listed it twice!
        path = /weather
...
```

Generally, if you encounter this error, the log file will give you the line number it happened in:

``` log
Apr 24 12:09:15 raven weewx[11480]: wxengine: Error while parsing configuration file /home/weewx/weewx.conf
Apr 24 12:09:15 raven weewx[11480]: wxengine: Unable to initialize main loop:
Apr 24 12:09:15 raven weewx[11480]: **** Duplicate keyword name at line 254.
Apr 24 12:09:15 raven weewx[11480]: **** Exiting. 
```

#### `configobj.NestingError` exception

This is a very similar error, and is caused by a misformed section nesting. For example:

```ini
[Reports]
    [[FTP]]]
        ...
```

Note the extra closing bracket on the subsection `FTP`.


### No barometer data

If everything appears normal except that you have no barometer data, the problem may be a mismatch between the unit system used for service `StdConvert` and the unit system used by service `StdQC`. For example:

```ini
[StdConvert]
    target_unit = METRIC
    ...

[StdQC]
    [[MinMax]]
        barometer = 28, 32.5
```

The problem is that you are requiring the barometer data to be between 28 and 32.5, but with the unit system set to `METRIC`, the data will be in the range 990 to 1050 or so!

The solution is to change the values to match the units in `StdConvert`, or specify the units in `MinMax`, regardless of the units in `StdConvert`. For example:

```ini hl_lines="7"
[StdConvert]
    target_unit = US
    ...

[StdQC]
    [[MinMax]]
        barometer = 950, 1100, mbar
```

### `Cheetah.NameMapper.NotFound` errors
If you get errors of the sort:

``` log
Apr 12 05:12:32 raven reportengine[3074]: filegenerator: Caught exception "<class 'NameMapper.NotFound'>"
Apr 12 05:12:32 raven reportengine[3074]: **** Message: "cannot find 'fubar' in template /home/weewx/skins/Standard/index.html.tmpl"
Apr 12 05:12:32 raven reportengine[3074]: **** Ignoring template and continuing.
```

you have a tag in your template that WeeWX does not recognize. In this example, it is the tag `$fubar` in the template `/home/weewx/skins/Standard/index.html.tmpl`.


### Dots in the plots

If you see dots instead of lines in the daily plots, you might want to change the graphing options or adjust the station's archive interval.

In a default configuration, a time period greater than 1% of the displayed timespan is considered to be a gap in data. So when the interval between data points is greater than about 10 minutes, the daily plots show dots instead of connected points.

Change the [line_gap_fraction](/custom/image_generator#line_gaps) option in `skin.conf` to control how much time is considered a break in data.

As for the archive interval, check the log file for an entry like this soon after WeeWX starts up:

```
Dec 30 10:54:17 saga weewx[10035]: wxengine: The archive interval in the configuration file
            (300) does not match the station hardware interval (1800).
Dec 30 10:54:17 saga weewx[10035]: wxengine: Using archive interval of 1800
```

In this example, interval in `weewx.conf` is 5 minutes, but the station interval is 30 minutes. When the interval in `weewx.conf` does not match the station's hardware interval, WeeWX defers to the station's interval.

Use the [`wee_device`](..//../utilities/utilities.htm#wee_device_utility) utility to change the station's interval.


### Spikes in the graphs

Occasionally you may see anomalous readings, typically manifested as spikes in the graphs. The source could be a flaky serial/USB connection, radio or other interference, a cheap USB-Serial adapter, low-quality sensors, or simply an anomalous reading.

Sensor quality matters. It is not unusual for some low-end hardware to report odd sensor readings occasionally (once every few days). Some sensors, such as solar radiation/UV, have a limited lifespan of about 5 years. The (analog) humidity sensors on older Vantage stations are known to deteriorate after a few years in wet environments.

If you frequently see anomalous data, first check the hardware.

To keep bad data from the database, add a quality control (QC) rule such as Min/Max bounds. See the [QC](weewx-config-file/stdqc-config.md) section for details.

To remove bad data from the database, you will have to do some basic SQL commands. For example, let's say the station emitted some very high temperatures and wind speeds for one or two readings. This is how to remove them:

1. Stop WeeWX
2. Make a copy of the archive database
``` bash
cp weewx.sdb weewx-YYMMDD.sdb
```
3. Verify the bad data exist where you think they exist
``` bash
sqlite3 weewx.sdb
sqlite> select dateTime,outTemp from archive where outTemp > 1000;
```
4. See whether the bad temperature and wind data happened at the same time
``` sql
sqlite> select dateTime,outTemp,windSpeed from archive where outTemp > 1000;
```
5. Remove the bad data by setting to NULL
``` sql
sqlite> update archive set windSpeed=NULL where outTemp > 1000;
sqlite> update archive set outTemp=NULL where outTemp > 1000;
```
6. Delete the aggregate statistics so that WeeWX can regenerate them without the anomalies
``` bash
sudo wee_database --drop-daily
```
7. Wtart WeeWX


### 'Database is locked' error
This seems to be a problem with the Raspberry Pi, *when using SQLite*. There is no analogous problem with MySQL databases. You will see errors in the system log that looks like this:

``` log
Feb 12 07:11:06 rpi weewx[20930]: ****    File "/usr/share/weewx/weewx/archive.py", line 118, in lastGoodStamp
Feb 12 07:11:06 rpi weewx[20930]: ****      _row = self.getSql("SELECT MAX(dateTime) FROM %s" % self.table)
Feb 12 07:11:06 rpi weewx[20930]: ****    File "/usr/share/weewx/weewx/archive.py", line 250, in getSql
Feb 12 07:11:06 rpi weewx[20930]: ****    File "/usr/share/weewx/weedb/sqlite.py", line 120, in execute
Feb 12 07:11:06 rpi weewx[20930]: ****      raise weedb.OperationalError(e)
Feb 12 07:11:06 rpi weewx[20930]: ****  OperationalError: database is locked
Feb 12 07:11:06 rpi weewx[20930]: ****      _cursor.execute(sql, sqlargs)
Feb 12 07:11:06 rpi weewx[20930]: ****    File "/usr/share/weewx/weedb/sqlite.py", line 120, in execute
Feb 12 07:11:06 rpi weewx[20930]: ****      raise weedb.OperationalError(e)
Feb 12 07:11:06 rpi weewx[20930]: ****  OperationalError: database is locked
```

We are still trying to decipher exactly what the problem is, but it seems that (many? most? all?) implementations of the SQLite 'C' access libraries on the RPi sleep for a full second if they find the database locked. This gives them only five chances within the 5 second timeout period before an exception is raised.

Not all Raspberry Pis have this problem. It seems to be most acute when running big templates with lots of queries, such as the forecast extension.

There are a few possible fixes:

* Increase the [timeout option](weewx-config-file/databases.md#sqlite).
* Use a high quality SD card in your RPi. There seems to be some evidence that faster SD cards are more immune to this problem.
* Trim the size of your templates to minimize the number of queries necessary.

None of these 'fixes' are very satisfying and we're trying to come up with a more robust solution.


### Funky symbols in plots

If your plots have strange looking symbols for units, such as degrees Fahrenheit (°F), that look something like this:

![funky degree sign](../images/funky_degree.png)


Then the problem may be that you are missing the fonts specified for the option `unit_label_font_path` in your `skin.conf` file and, instead, WeeWX is substituting a default font, which does not support the Unicode character necessary to make a degree sign. Look in section `[ImageGenerator]` for a line that looks like:
```
unit_label_font_path = /usr/share/fonts/truetype/freefont/FreeMonoBold.ttf
```
Make sure that the specified path (`/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf` in this case) actually exists. If it does not, on Debian operating systems (such as Ubuntu), you may be able to install the necessary fonts:
``` bash
sudo apt-get install fonts-freefont-ttf
sudo fc-cache -f -v
```
(On older systems, the package `fonts-freefont-ttf` may be called `ttf-freefont`). The first command installs the "Truetype" fonts, the second rebuilds the font cache. If your system does not have fc-cache command, then install it from the `fontconfig` package:
``` bash
sudo apt-get install fontconfig
```

If none of this works, or if you are on a different operating system, then you will have to change the option `unit_label_font_path` to point to something on your system which does support the Unicode characters you plan to use.


### UnicodeEncodeError
This problem is closely related to the ["Funky symbols"](#funky-symbols-in-plots) problem above. In this case, you may see errors in your log that look like:
``` log
May 14 13:35:23 web weewx[5633]: cheetahgenerator: Generated 14 files for report StandardReport in 1.27 seconds
May 14 13:35:23 web weewx[5633]: reportengine: Caught unrecoverable exception in generator weewx.imagegenerator.ImageGenerator
May 14 13:35:23 web weewx[5633]:         ****  'ascii' codec can't encode character u'\xe8' in position 5: ordinal not in range(128)
May 14 13:35:23 web weewx[5633]:         ****  Traceback (most recent call last):
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weewx/reportengine.py", line 139, in run
May 14 13:35:23 web weewx[5633]:         ****      obj.start()
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weewx/reportengine.py", line 170, in start
May 14 13:35:23 web weewx[5633]:         ****      self.run()
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weewx/imagegenerator.py", line 36, in run
May 14 13:35:23 web weewx[5633]:         ****      self.gen_images(self.gen_ts)
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weewx/imagegenerator.py", line 220, in gen_images
May 14 13:35:23 web weewx[5633]:         ****      image = plot.render()
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weeplot/genplot.py", line 175, in render
May 14 13:35:23 web weewx[5633]:         ****      self._renderTopBand(draw)
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/share/weewx/weeplot/genplot.py", line 390, in _renderTopBand
May 14 13:35:23 web weewx[5633]:         ****      top_label_size = draw.textsize(top_label, font=top_label_font)
May 14 13:35:23 web weewx[5633]:         ****    File "/usr/lib/python2.7/dist-packages/PIL/ImageDraw.py", line 278, in textsize
May 14 13:35:23 web weewx[5633]:         ****      return font.getsize(text)
May 14 13:35:23 web weewx[5633]:         ****  UnicodeEncodeError: 'ascii' codec can't encode character u'\xe8' in position 5: ordinal not in range(128)
May 14 13:35:23 web weewx[5633]:         ****  Generator terminated...
```
This is frequently caused by the necessary Truetype fonts not being installed on your computer and, instead, a default font is being substituted, which only knows how to plot ASCII characters. The cure is as before: install the font.


### Data is archived but some/all reports do not run

If WeeWX appears to be running normally but some or all reports are not being run, either all the time or periodically, the problem could be the inadvertant use or incorrect setting of the `report_timing` option in `weewx.conf`. The `report_timing` option allows the user to specify when some or all reports are run (see [*Scheduling report generation*](../../report_scheduling)). By default, the [_`report_timing`_](../weewx-config-file/stdreport-config/#report_timing) option is disabled and all reports are run each archive period.

To see if the `report_timing` option is causing reports to be skipped inspect the [log file](../../usersguide/running-weewx#monitoring-weewx). Any reports that are skipped due to the `report_timing` option will be logged as follows:
``` log
Apr 29 09:30:17 rosella weewx[3319]: reportengine: Report StandardReport skipped due to report_timing setting
```
If reports are being incorrectly skipped due to `report_timing`, then edit `weewx.conf` and check for a `report_timing` option in `[StdReport]`. Either remove all occurrences of `report_timing` to run all reports each archive period, or confirm the correct use and setting of the `report_timing` option.


### The wrong reports are being skipped by report_timing
If the [_`report_timing`_](../weewx-config-file/stdreport-config/#report_timing) option is being used, and the results are not as expected, there may be an error in the `report_timing` option. If there are errors in the `report_timing` parameter, the report will be run on each archive interval. First check the `report_timing` option parameters to ensure they are valid and there are no additonal spaces or other unwanted characters. Then check that the parameters are correctly set for the desired report generation times. For example, is the correct day of the week number being used if limiting the day of the week parameter. Refer to [*Scheduling report generation*](../../report_scheduling).

Check the [log file](../../usersguide/running-weewx#monitoring-weewx) for any entries relating to the reports concerned. Errors in the `report_timing` parameter and skipped reports are logged only when `debug=1` in `weewx.conf`.


## Meteorological problems
The pressure reported by WeeWX does not match the pressure on the console
Be sure that you are comparing the right values. There are three different types of pressure:

* **Station Pressure**: The _Station Pressure_ (SP), which is the raw, absolute pressure measured by the station. This is `pressure` in WeeWX packets and archive records.
* **Sea Level Pressure**: The _Sea Level Pressure_ (SLP) is obtained by correcting the Station Pressure for altitude and local temperature. This is `barometer` in WeeWX packets and archive records.
* **Altimeter**: The _Altimeter Setting_ (AS) is obtained by correcting the Station Pressure for altitude. This is `altimeter` in WeeWX packets and archive records.
Any station might require calibration. For some hardware, this can be done at the weather station console. Alternatively, use the `StdCalibrate` section to apply an offset.

If your station is significantly above (or below) sea level, be sure that the station altitude is specified properly. Also, be sure that any calibration results in a station pressure and/or barometric pressure that matches those reported by other stations in your area.

### Calibrating barometer does not change the pressure displayed by WeeWX
Be sure that the calibration is applied to the correct quantity.

The corrections in the `StdCalibrate` section apply only to raw values from the hardware; corrections are not applied to derived quantities.

The station hardware matters. Some stations report gauge pressure (`pressure`) while other stations report sea-level pressure (`barometer`). For example, if the hardware is a Vantage station, the correction must be applied to `barometer` since the Vantage station reports `barometer` and WeeWX calculates `pressure`. However, if the hardware is a FineOffset station, the correction must be applied to `pressure` since the FineOffset stations report `pressure` and WeeWX calculates `barometer`.

### The rainfall and/or rain rate reported by WeeWX do not match the console
First of all, be sure that you are comparing the right quantities. The value `rain` is the amount of rainfall observed in a period of time. The period of time might be a LOOP interval, in which case the `rain` is the amount of rain since the last LOOP packet. Because LOOP packets arrive quite frequently, this value is likely to be very small. Or the period of time might be an archive interval, in which case `rain` is the total amount of rain reported since the last archive record.

Some consoles report the amount of rain in the past hour, or the amount of rain since midnight.

The rain rate is a derived quantity. Some stations report a rain rate, but for those that do not, WeeWX will calculate the rain rate.

Finally, beware of calibration factors specific to the hardware. For example, the bucket type on a Vantage station must be specified when you set up the weather station. If you modify the rain bucket with a larger collection area, then you will have to add a multiplier in the `StdCalibrate` section.

To diagnose rain issues, run WeeWX directly so that you can see each LOOP packet and REC archive record. Tip the bucket to verify that each bucket tip is detected and reported by WeeWX. Verify that each bucket tip is converted to the correct rainfall amount. Then check the database to verify that the values are properly added and recorded.

### There is no wind direction when wind speed is zero
This is by design &mdash; if there is no wind, then the wind direction is undefined, represented by NULL in the database or `None` in Python. This policy is enforced by the `StdWXCalculate` service. If necessary, it can be overridden. See option [force_null](weewx-config-file/stdwxcalculate-config.md#winddir) in the [[StdWXCalculate]](weewx-config-file/stdwxcalculate-config.md) section.

WeeWX distinguishes between a value of zero and no value (NULL or None). However, some services do not make this distinction and replace a NULL or None with a clearly invalid value such as -999.