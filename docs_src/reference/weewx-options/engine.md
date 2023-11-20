# [Engine] 

This section is used to configure the internal service engine in WeeWX. It is
for advanced customization. Details on how to do this can be found in the section
[*Customizing the service engine*](../../custom/service-engine.md) of the *Customization Guide*.

## [[Services]]

Internally, WeeWX consists of many services, each responsible for some aspect
of the program's functionality. After an event happens, such as the arrival of
a new LOOP packet, any interested service gets a chance to do some useful work
on the event. For example, a service might manipulate the packet, print it
out, store it in a database, *etc*. This section controls which services are
loaded and in what order they get their opportunity to do that work. Before
WeeWX v2.6, this section held one, long, option called `service_list`, which
held the names of all the services that should be run. Since then, this list
has been broken down into smaller lists.

Service lists are run in the order given below.

| Service list       | Function                                              |
|--------------------|-------------------------------------------------------|
| `prep_services`    | Perform any actions before the main loop is run.      |
| `data_services`    | Augment data, before it is processed.                 |
| `process_services` | Process, filter, and massage the data.                |
| `xtype_services`   | Add derived types to the data stream.                 |
| `archive_services` | Record the data in a database.                        |
| `restful_services` | Upload processed data to an external RESTful service. |
| `report_services`  | Run any reports.                                      |

For reference, here is the standard set of services that are run with the
default distribution.

| Service list       | Function                                                                                                                                 |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `prep_services`    | `weewx.engine.StdTimeSynch`                                                                                                              |
| `data_services`	   |                                                                                                                                          |
| `process_services` | `weewx.engine.StdConvert` <br> `weewx.engine.StdCalibrate` <br> `weewx.engine.StdQC` <br> `weewx.wxservices.StdWXCalculate`              |
| `xtype_services`   | `weewx.wxxtypes.StdWXXTypes` <br/> `weewx.wxxtypes.StdPressureCooker`<br/> `weewx.wxxtypes.StdRainRater` <br/> `weewx.wxxtypes.StdDelta` |
| `archive_services` | `weewx.engine.StdArchive`                                                                                                                                                         |
| `restful_services` | `weewx.restx.StdStationRegistry` <br>`weewx.restx.StdWunderground` <br>`weewx.restx.StdPWSweather` <br>`weewx.restx.StdCWOP` <br>`weewx.restx.StdWOW` <br>`weewx.restx.StdAWEKAS` |
| `report_services`  | `weewx.engine.StdPrint` <br> `weewx.engine.StdReport`                                                                                                                             |

If you're the type who likes to clean out your car trunk after every use, then
you may also be the type who wants to pare this down to the bare minimum.
However, this will only make a slight difference in execution speed and memory
use.

#### prep_services

These services get called before any others. They are typically used to
prepare the console. For example, the service `weewx.wxengine.StdTimeSynch`,
which is responsible for making sure the console's clock is up-to-date, is a
member of this group.

#### data_services

Augment data before processing. Typically, this means adding fields to a LOOP
packet or archive record.

#### process_services

Services in this group tend to process any incoming data. They typically do
things like quality control, or unit conversion, or sensor calibration.

#### xtype_services

These are services that use the
[WeeWX XTypes](https://github.com/weewx/weewx/wiki/xtypes) system to augment
the data. Typically, they calculate derived variables such as `dewpoint`,
`ET`, `rainRate`, *etc*.

#### archive_services

Once data have been processed, services in this group archive them.

#### restful_services

RESTful services, such as the Weather Underground, or CWOP, are in this group.
They need processed data that have been archived, hence they are run after the
preceeding groups.

#### report_services

The various reporting services run in this group, including the standard
reporting engine.
