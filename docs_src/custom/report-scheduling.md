# Scheduling report generation

Normal WeeWX operation is to run each _[report](../reference/weewx-options/stdreport.md)_
defined in `weewx.conf` every archive period. While this may suit most
situations, there may be occasions when it is desirable to run a report less
frequently than every archive period. For example, the archive interval might
be 5 minutes, but you only want to FTP files every 30 minutes, once per day,
or at a set time each day.

There are two options to `[StdReport]` that provide the ability to control
when files are generated. The _`stale_age`_ option allows control over the
age of a file before it is regenerated, and the _`report_timing`_ option
allows precise control over when individual reports are run.

WeeWX also includes a utility [`weectl report
run`](../utilities/weectl-report.md#run-reports-on-demand) for
those times when you need to run a report independent of the interval timing.
For example, you might not want to wait for an archive interval to see if
your customizations worked.

!!! Note
    Although `report_timing` specifies when a given report should be generated,
    the generation of reports is still controlled by the WeeWX report cycle,
    so reports can never be generated more frequently than once every archive
    period.

    If your reports contain data that change more frequently that each archive
    interval, then you could run `weectl report run` separately, or consider
    uploading data to a real-time reporting solution such as MQTT.

## The stale_age option

The `stale_age` option applies to each file in a report. When `stale_age`
is specified, the file will be (re)generaed only when it is older than the
indicated age. The age is specified in seconds.

Details for the `stale_age` option are in the
[`[CheetahGenerator]`](../reference/skin-options/cheetahgenerator.md#stale_age) reference.

## The report_timing option

The `report_timing` option applies to each report. It uses a CRON-like
format to control when a report is to be run. While a CRON-like format is used,
the control of WeeWX report generation using the report_timing option is
confined completely to WeeWX and has no interraction with the system CRON
service.

The `report_timing` option consists of five parameters separated by
white-space:

```
report_timing = minutes hours day_of_month months day_of_week
```

The parameters are summarised in the following table:

<table>
<tr><th>Parameter</th><th>Function</th><th>Allowable values</th></tr>
<tr>
<td>minutes</td>
<td>Specifies the minutes of the hour when the report will be run</td>
<td>*, or numbers in the range 0..59 inclusive</td>
</tr>
<tr>
<td>hours</td>
<td>Specifies the hours of the day when the report will be run</td>
<td>*, or numbers in the range 0..23 inclusive</td>
</tr>
<tr>
<td>day_of_month</td>
<td>Specifies the days of the month when the report will be run</td>
<td>*, or numbers in the range 1..31 inclusive</td>
</tr>
<tr>
<td>months</td>
<td>Specifies the months of the year when the report will be run</td>
<td>
*, or numbers in the range 1..12 inclusive, or  
abbreviated names in the range jan..dec inclusive
</td>
</tr>
<tr>
<td>day_of_week</td>
<td>Specifies the days of the week when the report will be run</td>
<td>
*, or
numbers in the range 0..7 inclusive (0,7 = Sunday, 1 = Monday etc.), or  
abbreviated names in the range sun..sat inclusive
</td>
</tr>
</table>

The `report_timing` option may only be used in `weewx.conf`. When set in the
`[StdReport]` section, the option will apply to all reports listed under
`[StdReport]`. When specified within a report section, the option will
override any setting in `[StdReport]`, for that report. In this manner it
is possible to have different reports run at different times. The following
excerpt illustrates this:

```
[StdReport]

    report_timing = 0 * * * *

    [[AReport]]
        skin = SomeSkin

    [[AnotherReport]]
        skin = SomeOtherSkin
        report_timing = */10 * * * *
```

In this case, the report `AReport` would be run under control of the
`0 * * * *` setting (on the hour) and the report `AnotherReport` would be
run under control of the `*/10 * * * *` setting (every 10 minutes).

### How report_timing controls reporting

The syntax and interpretation of the report_timing parameters are largely the
same as those of the CRON service in many Unix and Unix-like operating systems.
The syntax and interpretation are outlined below.

When the report_timing option is in use WeeWX will run a report when the
minute, hour and month of year parameters match the report time, and at least
one of the two-day parameters (day of month or day of week) match the report
time. This means that non-existent times, such as "missing hours" during
daylight savings changeover, will never match, causing reports scheduled
during the "missing times" not to be run. Similarly, times that occur more
than once (again, during daylight savings changeover) will cause matching
reports to be run more than once.

!!! Note
    Report time does not refer to the time at which the report is run, but
    rather the date and time of the latest data the report is based upon. If
    you like, it is the effective date and time of the report. For normal
    WeeWX operation, the report time aligns with the dateTime of the most
    recent archive record. When reports are run using the `weectl report run` utility,
    the report time is either the dateTime of the most recent archive record
    (the default) or the optional timestamp command line argument.

!!! Note
    The day a report is to be run can be specified by two parameters; day of
    month and/or day of week. If both parameters are restricted (i.e., not an
    asterisk), the report will be run when either field matches the current
    time. For example,
    ```
    report_timing = 30 4 1,15 * 5
    ```
    would cause the report to be run at 4:30am on the 1st and 15th of each
    month as well as 4:30am every Friday.

### The relationship between report_timing and archive period

A traditional CRON service has a resolution of one minute, meaning that the
CRON service checks each minute whether to execute any commands. On the
other hand, the WeeWX report system checks which reports are to be run once
per archive period, where the archive period may be one minute, five minutes,
or some other user defined period. Consequently, the report_timing option may
specify a report to be run at some time that does not align with the WeeWX
archive period. In such cases the report_timing option does not cause a report
to be run outside the normal WeeWX report cycle, rather it will cause the
report to be run during the next report cycle. At the start of each report
cycle, and provided a report_timing option is set, WeeWX will check each
minute boundary from the current report time back until the report time of
the previous report cycle. If a match is found on **any** of these one minute
boundaries the report will be run during the report cycle. This may be best
described through some examples:

<table>
<tr>
<td>report_timing</td>
<td>Archive period</tD>
<td>When the report will be run</td>
</tr>
<tr>
<td>0 * * * *</td>
<td>5 minutes</tD>
<td>The report will be run only during the report cycle commencing on the hour.</td>
</tr>
<tr>
<td>5 * * * *</td>
<td>5 minutes</td>
<td>The report will be run only during the report cycle commencing at 5 minutes past the hour.</td>
</tr>
<tr>
<td>3 * * * *</td>
<td>5 minutes</td>
<td>The report will be run only during the report cycle commencing at 5 minutes past the hour.</td>
</tr>
<tr>
<td>10 * * * *</td>
<td>15 minutes</td>
<td>The report will be run only during the report cycle commencing at 15 minutes past the hour</td>
</tr>
<tr>
<td>10,40 * * * *</td>
<td>15 minutes</td>
<td>The report will be run only during the report cycles commencing at 15 minutes past the hour and 45 minutes past the hour.</td>
</tr>
<tr>
<td>5,10 * * * *</td>
<td>15 minutes</td>
<td>The report will be run once only during the report cycle commencing at 15 minutes past the hour.</td>
</tr>
</table>


### Lists, ranges and steps

The report_timing option supports lists, ranges, and steps for all parameters.
Lists, ranges, and steps may be used as follows:

* _Lists_. A list is a set of numbers (or ranges) separated by commas, for
  example `1, 2, 5, 9` or `0-4, 8-12`. A match with any of the elements of the
  list will result in a match for that particular parameter. If the examples
  were applied to the minutes parameter, and subject to other parameters in
  the report_timing option, the report would be run at minutes 1, 2, 5, and
  9 and 0, 1, 2, 3, 4, 8, 9, 10, 11, and 12 respectively. Abbreviated month
  and day names cannot be used in a list.

* _Ranges_. Ranges are two numbers separated with a hyphen, for example `8-11`.
  The specified range is inclusive. A match with any of the values included
  in the range will result in a match for that particular parameter. If the
  example was applied to the hours parameter, and subject to other parameters
  in the report_timing option, the report would be run at hours 8, 9, 10, and
  11. A range may be included as an element of a list. Abbreviated month and
  day names cannot be used in a range.

* _Steps_. A step can be used in conjunction with a range or asterisk and are
  denoted by a '/' followed by a number. Following a range with a step
  specifies skips of the step number's value through the range. For example,
  `0-12/2` used in the hours parameter would, subject to other parameter in the
  report_timing option, run the report at hours 0, 2, 4, 6, 8, and 12. Steps
  are also permitted after an asterisk in which case the skips of the step
  number's value occur through the all possible values of the parameter. For
  example, `*/3` can be used in the hours parameter to, subject to other
  parameter in the report_timing option, run the report at hours 0, 3, 6,
  9, 12, 15, 18, and 21.

### Nicknames

The report_timing option supports a number of time specification 'nicknames'.
These nicknames are prefixed by the '@' character and replace the five
parameters in the report_timing option. The nicknames supported are:

<table>
<tr>
<td>Nickname</td>
<td>Equivalent setting</td>
<td>When the report will be run</td>
</tr>
<tr>
<td>@yearly<br/>@annually</td>
<td>0 0 1 1 *</td>
<td>Once per year at midnight on 1 January.</td>
</tr>
<tr>
<td>@monthly</td>
<td>0 0 1 * *</td>
<td>Monthly at midnight on the 1st of the month.</td>
</tr>
<tr>
<td>@weekly</td>
<td>0 0 * * 0</td>
<td>Every week at midnight on Sunday.</td>
</tr>
<tr>
<td>@daily</td>
<td>0 0 * * *</td>
<td>Every day at midnight.</td>
</tr>
<tr>
<td>@hourly</td>
<td>0 * * * *</td>
<td>Every hour on the hour.</td>
</tr>
</table>


### Examples of report_timing

Numeric settings for report_timing can be at times difficult to understand due
to the complex combinations of parameters. The following table shows a number
of example report_timing options and the corresponding times when the report
would be run.

<table>
<tr>
<td>report_timing</td>
<td>When the report will be run</td>
</tr>
<tr>
<td>* * * * *</td>
<td>Every archive period. This setting is effectively the default WeeWX method of operation.</td>
</tr>
<tr>
<td>25 * * * *</td>
<td>25 minutes past every hour.</td>
</tr>
<tr>
<td>0 * * * *</td>
<td>Every hour on the hour.</td>
</tr>
<tr>
<td>5 0 * * *</td>
<td>00:05 daily.</td>
</tr>
<tr>
<td>25 16 * * *</td>
<td>16:25 daily.</td>
</tr>
<tr>
<td>25 16 1 * *</td>
<td>16:25 on the 1st of each month.</td>
</tr>
<tr>
<td>25 16 1 2 *</td>
<td>16:25 on the 1st of February.</td>
</tr>
<tr>
<td>25 16 * * 0</td>
<td>1:25 each Sunday.</td>
</tr>
<tr>
<td>*/10 * * * *</td>
<td>On the hour and 10, 20, 30, 40 and 50 mnutes past the hour.</td>
</tr>
<tr>
<td>*/9 * * * *</td>
<td>On the hour and 9, 18, 27, 36, 45 and 54 minutes past the hour.</td>
</tr>
<tr>
<td>*/10 */2 * * *</td>
<td>0, 10, 20, 30, 40 and 50 minutes after the even hour.</td>
</tr>
<tr>
<td>* 6-17 * * *</td>
<td>Every archive period from 06:00 (inclusive) up until, but excluding, 18:00.</td>
</tr>
<tr>
<td>* 1,4,14 * * *</td>
<td>Every archive period in the hour starting 01:00 to 01:59, 04:00 to 04:59 amd 14:00 to 14:59 (Note excludes report times at 02:00, 05:00 and 15:00).</td>
</tr>
<tr>
<td>0 * 1 * 0,3</td>
<td>On the hour on the first of the month and on the hour every Sunday and Wednesday.</td>
</tr>
<tr>
<td>* * 21,1-10/3 6 *</td>
<td>Every archive period on the 1st, 4th, 7th, 10th and 21st of June.</td>
</tr>
<tr>
<td>@monthly</td>
<td>Midnight on the 1st of the month.</td>
</tr>
</table>

### The `weectl report run` utility and the report_timing option

The `report_timing` option is ignored when using the `weectl report run` utility.
