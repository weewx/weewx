# wee_debug

Troubleshooting problems when running WeeWX often involves analysis of a number
of pieces of seemingly disparate system and WeeWX related information. The
`wee_debug` utility gathers all this information together into a single output
to make troubleshooting easier. The `wee_debug` utility is particularly useful
for new users as the output may be redirected to a file then emailed or posted
to a forum to assist in remote troubleshooting.

Specify `--help` to see how it is used:

```
wee_debug --help
```
```
Usage: wee_debug --help
       wee_debug --info
            [CONFIG_FILE|--config=CONFIG_FILE]
            [--output|--output DEBUG_PATH]
            [--verbosity=0|1|2]
       wee_debug --version

Description:

Generate a standard suite of system/weewx information to aid in remote
debugging. The wee_debug output consists of two parts, the first part containing
a snapshot of relevant system/weewx information and the second part a parsed and
obfuscated copy of weewx.conf. This output can be redirected to file and posted
when seeking assistance via forums or email.

Actions:

--info           Generate a debug report.

Options:
  -h, --help            show this help message and exit
  --config=CONFIG_FILE  Use configuration file CONFIG_FILE.
  --info                Generate weewx debug output.
  --output              Write wee_debug output to DEBUG_PATH. DEBUG_PATH
                        includes path and file name. Default is
                        /var/tmp/weewx.debug.
  --verbosity=N         How much detail to display, 0-2, default=1.
  --version             Display wee_debug version number.

wee_debug will attempt to obfuscate obvious personal/private information in
weewx.conf such as user names, passwords and API keys; however, the user
should thoroughly check the generated output for personal/private information
before posting the information publicly.
```

### --config=FILENAME

The utility is pretty good about guessing where the configuration file is,
but if you have an unusual installation or multiple stations, you may have to
tell it explicitly. You can do this by either putting the location directly in
the command line:

```
wee_debug /home/weewx/weewx.conf --info
```

or by using option `--config`:

```
wee_debug --config=/home/weewx/weewx.conf --info
```

### --info

This action generates a debug report which can be sent off for remote
debugging.

```
wee_debug --info
```

!!! Warning
    The `wee_debug` output includes a copy of the WeeWX config file (typically
    `weewx.conf`) and whilst `wee_debug` attempts to obfuscate any personal or
    sensitive information, the user should carefully check the `wee_debug`
    output for any remaining personal or sensitive information before emailing
    or posting the output publicly.

This results in output something like this:

```
Using verbosity=1, displaying most info

wee_debug output will be sent to stdout(console)

Using configuration file /home/weewx/weewx.conf
Using database binding 'wx_binding', which is bound to database 'archive_mysql'

System info
  CPU implementer:        0x41
  Features:               half thumb fastmult vfp edsp java tls
  CPU architecture:       7
  BogoMIPS:               2.00
  Hardware:               BCM2708
  CPU revision:           7
  CPU part:               0xb76
  model name:             ARMv6-compatible processor rev 7 (v6l)
  Serial:                 000000009581b554
  processor:              0
  CPU variant:            0x0
  Revision:               000e

  Operating system:       debian 7.8
                          Linux rosella 4.1.6+ #810 PREEMPT Tue Aug 18 15:19:58 BST 2015 armv6l
  1 minute load average:  0.19
  5 minute load average:  0.15
  15 minute load average: 0.12

General weewx info
  Weewx version 3.2.1 detected.

Station info
  Station type: Simulator
  Driver:       weewx.drivers.simulator

Driver info
[Simulator]
    # This section is for the weewx weather station simulator

    # The time (in seconds) between LOOP packets.
    loop_interval = 2.5

    # The simulator mode can be either 'simulator' or 'generator'.
    # Real-time simulator. Sleep between each LOOP packet.
    mode = simulator
    # Generator.  Emit LOOP packets as fast as possible (useful for testing).
    #mode = generator

    # The start time. If not specified, the default is to use the present time.
    #start = 2011-01-01 00:00

    # The driver to use:
    driver = weewx.drivers.simulator

Currently installed extensions
Extension Name    Version   Description
Weewx-WD          1.2.0b1   Weewx support for Weather Display Live, SteelSeries Gauges and Carter Lake/Saratoga weather web site templates.

Archive info
  Database name:        weewx
  Table name:           archive
  Unit system:          16(METRIC)
  First good timestamp: 2013-01-01 00:00:00 AEST (1356962400)
  Last good timestamp:  2015-09-06 02:15:00 AEST (1441469700)
  Number of records:    281178
  weewx (weewx.conf) is set to use an archive interval of 300 seconds.
  The station hardware was not interrogated in determining archive interval.

Databases configured in weewx.conf
  Database name:        weewx
  Database driver:      weedb.mysql
  Database host:        localhost

  Database name:        wdsupp
  Database driver:      weedb.mysql
  Database host:        localhost

  Database name:        weewxwd
  Database driver:      weedb.mysql
  Database host:        localhost


Parsed and obfuscated weewx.conf
# WEEWX CONFIGURATION FILE
#
# Copyright (c) 2009-2015 Tom Keffer &lt;tkeffer@gmail.com&gt;
# See the file LICENSE.txt for your rights.

##############################################################################

# This section is for general configuration information.

... content removed for conciseness ...

#   This section configures the internal weewx engine.

[Engine]

    [[Services]]
        # This section specifies the services that should be run. They are
        # grouped by type, and the order of services within each group
        # determines the order in which the services will be run.
        prep_services = weewx.engine.StdTimeSynch
        data_services = ,
        process_services = weewx.engine.StdConvert, weewx.engine.StdCalibrate, weewx.engine.StdQC, weewx.wxservices.StdWXCalculate, user.weewxwd3.WdWXCalculate
        archive_services = weewx.engine.StdArchive, user.weewxwd3.WdArchive, user.weewxwd3.WdSuppArchive
        restful_services = weewx.restx.StdStationRegistry, weewx.restx.StdWunderground, weewx.restx.StdPWSweather, weewx.restx.StdCWOP, weewx.restx.StdWOW, weewx.restx.StdAWEKAS, user.sync.SyncService
        report_services = weewx.engine.StdPrint, weewx.engine.StdReport

################################################################################

wee_debug report successfully generated
```

### --output[=FILENAME]

By default, `wee_debug` sends its output to the system "standard output"
(`stdout`) unless the `--output` option is used.

The option `--output` with no parameter sends output to the default file
`/var/tmp/weewx.debug`.

```
wee_debug --info --output
```

The option `--output` with a specified file will send it to that file.

```
wee_debug --info --output /home/weewx/another.debug
```

### --verbosity=(0|1|2)

The amount of information included in the `wee_debug` output can be changed
using the `--verbosity` option. The `--verbosity` option can be set to
0, 1 or 2 with each higher level successively displaying more information. The
default level is 1. The information displayed for each level is:

<table class="no_indent">
  <tr class="first_row">
    <td>Level</td>
    <td>Included Information</td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="8"><span class="code">--verbosity 0</span></td>
    <td>path and name of WeeWX config file
    </td>
  </tr>
  <tr>
    <td>name of WeeWX database binding used</td>
  </tr>
  <tr>
    <td>operating system version</td>
  </tr>
  <tr>
    <td>WeeWX version number</td>
  </tr>
  <tr>
    <td>WeeWX station type and driver name</td>
  </tr>
  <tr>
    <td>summary of currently installed extensions</td>
  </tr>
  <tr>
    <td>summary of WeeWX archive</td>
  </tr>
  <tr>
    <td>parsed and obfuscated WeeWX config file (usually `weewx.conf`)
    </td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="5"><span class="code">--verbosity 1</span></td>
    <td>as per <span class='code'>--verbosity 0</span></td>
  </tr>
  <tr>
    <td>cpu info summary</td>
  </tr>
  <tr>
    <td>system load averages</td>
  </tr>
  <tr>
    <td>driver config extract from WeeWX config file
    </td>
  </tr>
  <tr>
    <td>summary of databases configured in WeeWX config file
    </td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="3"><span class="code">--verbosity 2</span></td>
    <td>as per <span class="code">--verbosity 1</span></td>
  </tr>
  <tr>
    <td>list of supported SQL keys</td>
  </tr>
  <tr>
    <td>list of supported observation types</td>
  </tr>
</table>
