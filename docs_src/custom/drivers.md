# Porting to new hardware {#porting}

Naturally, this is an advanced topic but, nevertheless, I'd like to
encourage any Python wizards out there to give it a try. Of course, I
have selfish reasons for this: I don't want to have to buy every
weather station ever invented, and I don't want my roof to look like a
weather station farm!

A *driver* communicates with hardware. Each driver is a single python
file that contains the code that is the interface between a device and
WeeWX. A driver may communicate directly with hardware using a MODBus,
USB, serial, or other physical interface. Or it may communicate over a
network to a physical device or a web service.

## General guidelines

-   The driver should emit data as it receives it from the hardware (no
    caching).
-   The driver should emit only data it receives from the hardware (no
    "filling in the gaps").
-   The driver should not modify the data unless the modification is
    directly related to the hardware (*e.g.*, decoding a
    hardware-specific sensor value).
-   If the hardware flags "bad data", then the driver should emit a
    null value for that datum (Python `None`).
-   The driver should not calculate any derived variables (such as
    dewpoint). The service `StdWXService` will do that.
-   However, if the hardware emits a derived variable, then the driver
    should emit it.

## Implement the driver

Create a file in the user directory, say `mydriver.py`. This file
will contain the driver class as well as any hardware-specific code. Do
not put it in the `weewx/drivers` directory, or it will be deleted
when you upgrade WeeWX.

Inherit from the abstract base class
`weewx.drivers.AbstractDevice`. Try to implement as many of its
methods as you can. At the very minimum, you must implement the first
three methods, `loader`, `hardware_name`, and
`genLoopPackets`.

#### loader()

This is a factory function that returns an instance of your driver. It
has two arguments: the configuration dictionary, and a reference to the
WeeWX engine.

#### hardware_name

This can as implemented as either an attribute, or as a [property
function](https://docs.python.org/3/library/functions.html#property). It should
return a string with a short nickname for the hardware, such as `"ACME X90"`

#### genLoopPackets()

This should be a Python [generator
function](https://wiki.python.org/moin/Generators) that yields loop
packets, one after another. Don't worry about stopping it: the engine
will do this when an archive record is due. A "loop packet" is a
dictionary. At the very minimum it must contain keys for the observation
time and for the units used within the packet.

<table>
    <caption>Required keys</caption>
    <tbody>
    <tr>
        <td class="code first_col">dateTime</td>
        <td>The time of the observation in unix epoch time.</td>
    </tr>
    <tr>
        <td class="code first_col">usUnits</td>
        <td>
The unit system used. <span class="code">weewx.US</span> for US customary,
<span class="code">weewx.METRICWX</span>, or
<span class="code">weewx.METRIC</span> for metric. See the
<a href="../../reference/units"><em>Units</em></a> for their exact definitions.
The dictionaries <span class="code">USUnits</span>,
<span class="code">MetricWXUnits</span>, and
<span class="code">MetricUnits</span> in file
<span class="code">units.py</span>, can also be useful.
        </td>
    </tr>
    </tbody>
</table>

Then include any observation types you have in the dictionary. Every
packet need not contain the same set of observation types. Different
packets can use different unit systems, but all observations within a
packet must use the same unit system. If your hardware is capable of
measuring an observation type but, for whatever reason, its value is bad
(maybe a bad checksum?), then set its value to `None`. If your
hardware is incapable of measuring an observation type, then leave it
out of the dictionary.

A couple of observation types are tricky, in particular, `rain`.
The field `rain` in a LOOP packet should be the amount of rain
that has fallen *since the last packet*. Because LOOP packets are
emitted fairly frequently, this is likely to be a small number. If your
hardware does not provide this value, you might have to infer it from
changes in whatever value it provides, for example changes in the daily
or monthly rainfall.

Wind is another tricky one. It is actually broken up into four different
observations: `windSpeed`, `windDir`, `windGust`,
and `windGustDir`. Supply as many as you can. The directions
should be compass directions in degrees (0=North, 90=East, etc.).

Be careful when reporting pressure. There are three observations related
to pressure. Some stations report only the station pressure, others
calculate and report sea level pressures.

<table>
    <caption>Pressure types</caption>
    <tbody>
    <tr>
        <td class="code first_col">pressure</td>
        <td>
The <em>Station Pressure</em> (SP), which is the raw, absolute pressure
measured by the station. This is the true barometric pressure for the station.
        </td>
    </tr>
    <tr>
        <td class="code first_col">barometer</td>
        <td>
The <em>Sea Level Pressure</em> (SLP) obtained by correcting the <em>Station
Pressure</em> for altitude and local temperature. This is the pressure reading
most commonly used by meteorologist to track weather systems at the surface,
and this is the pressure that is uploaded to weather services by WeeWX. It is
the station pressure reduced to mean sea level using local altitude and local
temperature.
        </td>
    </tr>
    <tr>
        <td class="code first_col">altimeter</td>
        <td>
The <em>Altimeter Setting</em> (AS) obtained by correcting the <em>Station
Pressure</em> for altitude. This is the pressure reading most commonly heard
in weather reports. It is not the true barometric pressure of a station, but
rather the station pressure reduced to mean sea level using altitude and an
assumed temperature average.
        </td>
    </tr>
    </tbody>
</table>

#### genArchiveRecords()

If your hardware does not have an archive record logger, then WeeWX can
do the record generation for you. It will automatically collect all the
types it sees in your loop packets then emit a record with the averages
(in some cases the sum or max value) of all those types. If it doesn't
see a type, then it won't appear in the emitted record.

However, if your hardware does have a logger, then you should implement
method `genArchiveRecords()` as well. It should be a generator
function that returns all the records since a given time.

#### archive_interval

If you implement function `genArchiveRecords()`, then you should
also implement `archive_interval` as either an attribute, or as a
[property
function](https://docs.python.org/3/library/functions.html#property). It
should return the archive interval in seconds.

#### getTime()

If your hardware has an onboard clock and supports reading the time from
it, then you may want to implement this method. It takes no argument. It
should return the time in Unix Epoch Time.

#### setTime()

If your hardware has an onboard clock and supports *setting* it, then
you may want to implement this method. It takes no argument and does not
need to return anything.

#### closePort()

If the driver needs to close a serial port, terminate a thread, close a
database, or perform any other activity before the application
terminates, then you must supply this function. WeeWX will call it if it
needs to shut down your console (usually in the case of an error).

## Define the configuration

You then include a new section in the configuration file
`weewx.conf` that includes any options your driver needs. It
should also include an entry `driver` that points to where your
driver can be found. Set option `station_type` to your new
section type and your driver will be loaded.

## Examples

The `fileparse` driver is perhaps the simplest example of a WeeWX
driver. It reads name-value pairs from a file and uses the values as
sensor 'readings'. The code is actually packaged as an extension,
located in `examples/fileparse`, making it a good example of not
only writing a device driver, but also of how to package an extension.
The actual driver itself is in
`examples/fileparse/bin/user/fileparse.py`.

Another good example is the simulator code located in
`weewx/drivers/simulator.py`. It's dirt simple, and you can
easily play with it. Many people have successfully used it as a starting
point for writing their own custom driver.

The Ultimeter (`ultimeter.py`) and WMR100 (`wmr100.py`)
drivers illustrate how to communicate with serial and USB hardware,
respectively. They also show different approaches for decoding data.
Nevertheless, they are pretty straightforward.

The driver for the Vantage series is by far the most complicated. It
actually multi-inherits from not only `AbstractDevice`, but also
`StdService`. That is, it also participates in the engine as a
service.

Naturally, there are a lot of subtleties that have been glossed over in
this high-level description. If you run into trouble, look for help in
the [weewx-development](https://groups.google.com/g/weewx-development) group.
