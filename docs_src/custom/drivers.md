# Porting to new hardware {#porting}

Naturally, this is an advanced topic but, nevertheless, I'd like to encourage
any Python wizards out there to give it a try. Of course, I have selfish reasons
for this: I don't want to have to buy every weather station ever invented, and I
don't want my backyard to look like a weather station farm!

A *driver* communicates with hardware. Each driver is a single Python file that
contains the code that is the interface between a device and WeeWX. A driver may
communicate directly with hardware using a MODBus, USB, serial, or other
physical interface. Or it may communicate over a network to a physical device or
a web service.

## General guidelines

- The driver should emit data as it receives it from the hardware (no caching).
- The driver should emit only data it receives from the hardware (no
  "filling in the gaps").
- The driver should not modify the data unless the modification is directly
  related to the hardware (*e.g.*, decoding a hardware-specific sensor value).
- If the hardware flags "bad data", then the driver should emit a null value for
  that datum (Python `None`).
- The driver should not calculate any derived variables (such as dewpoint). The
  service `StdWXService` will do that.
- However, if the hardware emits a derived variable, then the driver should emit
  it.

## Implement the driver

Create a file in the user directory, say `mydriver.py`. This file will contain
the driver class as well as any hardware-specific code. Do not put it in the
`weewx/drivers` directory, or it will be deleted when you upgrade WeeWX.

Inherit from the abstract base class
`weewx.drivers.AbstractDevice`. Try to implement as many of its methods as you
can. At the very minimum, you must implement the first three methods, `loader`,
`hardware_name`, and `genLoopPackets`.

#### loader ()

This is a factory function that returns an instance of your driver. It has two
arguments: the configuration dictionary, and a reference to the WeeWX engine.

#### hardware_name

This can as implemented as either an attribute, or as
a [property function](https://docs.python.org/3/library/functions.html#property).
It should return a string with a short nickname for the hardware, such as
`"ACME X90"`.

#### genLoopPackets ()

This should be a
Python [generator function](https://docs.python.org/3/reference/expressions.html#yieldexpr)
that yields loop packets, one after another. Don't worry about stopping it: the
engine will do this when an archive record is due. A "loop packet" is a
dictionary. At the very minimum it must contain keys for the observation time
and for the units used within the packet.

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
<a href="../reference/units"><em>Units</em></a> for their exact definitions.
The dictionaries <span class="code">USUnits</span>,
<span class="code">MetricWXUnits</span>, and
<span class="code">MetricUnits</span> in file
<span class="code">units.py</span>, can also be useful.
        </td>
    </tr>
    </tbody>
</table>

Then include any observation types available from the hardware in the
dictionary. Every packet need not contain the same set of observation types.
Different packets can use different unit systems, but all observations within a
packet must use the same unit system. If your hardware is capable of measuring
an observation type but, for whatever reason, its value is bad (maybe a bad
checksum?), then set its value to `None`. If your hardware is incapable of
measuring an observation type, then leave it out of the dictionary.

A couple of observation types are tricky, in particular, `rain`. The field
`rain` in a LOOP packet should be the amount of rain that has fallen *since the
last packet*. Because LOOP packets are emitted fairly frequently, this is likely
to be a small number. If your hardware does not provide this value, you might
have to infer it from changes in whatever value it provides, for example changes
in the daily or monthly rainfall.

Wind is another tricky one. It is actually broken up into four different
observations: `windSpeed`, `windDir`, `windGust`, and `windGustDir`. Supply as
many as you can. The directions should be compass directions in degrees
(0=North, 90=East, etc.).

Be careful when reporting pressure. There are three observations related to
pressure. Some stations report only the station pressure, others calculate and
report sea level pressures.

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

#### genArchiveRecords ()

If your hardware does not have an archive record logger, then WeeWX can do the
record generation for you. It will automatically collect all the types it sees
in your loop packets then emit a record with the averages (in some cases the sum
or max value) of all those types. If it doesn't see a type, then it won't appear
in the emitted record.

However, if your hardware does have a logger, then you should implement method
`genArchiveRecords()` as well. It should be a generator function that returns
all the records since a given time.

#### archive_interval

If you implement function `genArchiveRecords()`, then you should also implement
`archive_interval` as either an attribute, or as a
[property function](https://docs.python.org/3/library/functions.html#property).
It should return the archive interval in seconds.

#### getTime ()

If your hardware has an onboard clock and supports reading the time from it,
then you may want to implement this method. It takes no argument. It should
return the time in Unix Epoch Time.

#### setTime ()

If your hardware has an onboard clock and supports *setting* it, then you may
want to implement this method. It takes no argument and does not need to return
anything.

#### closePort ()

If the driver needs to close a serial port, terminate a thread, close a
database, or perform any other activity before the application terminates, then
you must supply this function. WeeWX will call it if it needs to shut down your
console (usually in the case of an error).

## Hardware that pushes {#listener}

Some hardware never answers a request. It uploads on its own schedule, so a driver for
it has to be a server rather than a client. Ecowitt gateways and consoles, Acurite
bridges, and WeatherFlow hardware all work this way.

Use `weewx.listener.HTTPListener` for these. It owns the socket, the thread, and the
queue, which leaves the driver with the part that actually differs between devices.

``` python
from weewx.listener import HTTPListener

class MyDriver(weewx.drivers.AbstractDevice):

    def __init__(self, **stn_dict):
        self.listener = HTTPListener(**stn_dict)

    def genLoopPackets(self):
        for request in self.listener:
            packet = self.parse(request.text)
            if packet:
                yield packet

    def closePort(self):
        self.listener.close()
```

Each request carries `method`, `path`, `query`, `body`, `headers`, and
`client_address`. Use `request.text` if the device may use either protocol: it returns
the body of a POST, and the query string of a GET.

Most devices treat an upload as failed until they have read a response, and what they
expect is part of their protocol. Give the listener a string, or a function of the
request:

``` python
self.listener = HTTPListener(response='{"errcode":"0","errmsg":"ok"}',
                             content_type='application/json',
                             **stn_dict)
```

Options may be given as strings, so a driver can pass its configuration stanza
straight through:

<table>
  <tr class="first_row">
    <td>Option</td>
    <td>Default</td>
    <td>Meaning</td>
  </tr>
  <tr>
    <td class="code">port</td>
    <td>80</td>
    <td>The port to listen on. Ports below 1024 need root.</td>
  </tr>
  <tr>
    <td class="code">address</td>
    <td><i>every interface</i></td>
    <td>The address to bind to. Use <span class="code">localhost</span> when a reverse
        proxy sits in front.</td>
  </tr>
  <tr>
    <td class="code">path</td>
    <td><i>every path</i></td>
    <td>Accept this path only, <i>e.g.</i>
        <span class="code">/data/report/</span>. Anything else gets a 404.</td>
  </tr>
  <tr>
    <td class="code">max_body</td>
    <td>65536</td>
    <td>Largest body accepted, in bytes. Bigger requests get a 413.</td>
  </tr>
  <tr>
    <td class="code">socket_timeout</td>
    <td>20</td>
    <td>How long an idle client may hold a connection open, in seconds.</td>
  </tr>
  <tr>
    <td class="code">queue_size</td>
    <td>10</td>
    <td>How many requests may wait to be picked up. Beyond that, the oldest is
        dropped and a warning is logged.</td>
  </tr>
  <tr>
    <td class="code">allowed_hosts</td>
    <td><i>anywhere</i></td>
    <td>Accept requests from these addresses only.</td>
  </tr>
  <tr>
    <td class="code">token</td>
    <td><i>none</i></td>
    <td>Require this token, given as query parameter
        <span class="code">token</span>, in header
        <span class="code">X-Auth-Token</span>, or as a bearer token in
        <span class="code">Authorization</span>. Anything else gets a 403.</td>
  </tr>
  <tr>
    <td class="code">trust_proxy</td>
    <td>False</td>
    <td>Take the client address from <span class="code">X-Forwarded-For</span>. Only
        set this when a proxy you control sets that header.</td>
  </tr>
  <tr>
    <td class="code">log_raw</td>
    <td>False</td>
    <td>Log every request body at debug level. This is what you turn on when a sensor
        is missing from the data.</td>
  </tr>
</table>

The socket is bound when the listener is created, so a port that is already in use is
reported where the driver is built.

Anyone who can reach the port can post readings, so the listener offers three ways to
narrow that down: `allowed_hosts`, `token`, and `path`. Hardware that can only be given
a URL, which is most of it, can still carry a secret in the path:

``` ini
[MyDriver]
    driver = user.mydriver
    port = 8000
    path = /a8f3c1e0/report
```

None of this is a substitute for TLS, and the listener does not offer any. Put a reverse
proxy in front for that, and set `trust_proxy` so the driver still sees the real client
address.

What the listener does not check is whatever the device carries in its own payload, such
as the Ecowitt `PASSKEY` or a Weather Underground station ID. Those belong to the
protocol, so they are the driver's to verify.

### Hardware that broadcasts

Some hardware does not post at all. It puts a datagram on the local network and moves
on, e.g. WeatherFlow on port 50222, or a Davis WeatherLink Live on 22222. Use
`weewx.listener.UDPListener` for those. Same queue, same iteration, no response to send:

``` python
from weewx.listener import UDPListener

self.listener = UDPListener(port=50222)
```

It takes `port`, `address`, `max_body`, `allowed_hosts`, `log_raw`, and `queue_size`
with the same meanings, plus `reuse_address`. That one defaults to `True`, so other
programs on the machine can read the same broadcasts. Set it to `False` to have the port
to yourself.

Two differences are worth knowing. UDP has no way to refuse an oversized datagram, so
`max_body` truncates rather than rejects. And a datagram carries no path, no headers and
no token, so `allowed_hosts` is the only filter there is.

## Define the configuration

You then include a new section in the configuration file `weewx.conf` that
includes any options your driver needs. It should also include an entry `driver`
that points to where your driver can be found. Set option
`station_type` to your new section type and your driver will be loaded.

## Examples

The `fileparse` driver is perhaps the simplest example of a WeeWX driver. It
reads name-value pairs from a file and uses the values as sensor "readings". The
code is actually packaged as an extension, located in `examples/fileparse`,
making it a good example of not only writing a device driver, but also of how to
package an extension. The actual driver itself is in
`examples/fileparse/bin/user/fileparse.py`.

Another good example is the simulator code located in
`weewx/drivers/simulator.py`. It's dirt simple, and you can easily play with it.
Many people have successfully used it as a starting point for writing their own
custom driver.

The Ultimeter (`ultimeter.py`) and WMR100 (`wmr100.py`)
drivers illustrate how to communicate with serial and USB hardware,
respectively. They also show different approaches for decoding data.
Nevertheless, they are pretty straightforward.

The driver for the Vantage series is by far the most complicated. It actually
multi-inherits from not only `AbstractDevice`, but also
`StdService`. That is, it also participates in the engine as a service.

Naturally, there are a lot of subtleties that have been glossed over in this
high-level description. If you run into trouble, look for help in
the [weewx-development](https://groups.google.com/g/weewx-development) group.
