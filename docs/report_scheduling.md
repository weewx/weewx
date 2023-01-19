# Scheduling report generation

Normal WeeWX operation is to run each _[report](../usersguide/weewx-config-file/stdreport-config)_ defined in `weewx.conf` every archive period. While this may suit most situations, there may be occasions when it is desirable to run a report less frequently than every archive period. For example, the archive interval might be 5 minutes, but you only want to FTP files every 30 minutes, once per day, or at a set time each day. WeeWX has two mechanisms that provide the ability to control when files are generated. The [_`stale_age`_](#stale_age) option allows control over the age of a file before it is regenerated, and the [_`report_timing`_](#report_timing) option allows precise control over when individual reports are run.

!!! Note
    While `report_timing` specifies when a given report should be generated, the generation of reports is still controlled by the WeeWX report cycle, so reports can never be generated more frequently than once every archive period.

### The report_timing option

The report_timing option uses a CRON-like format to control when a report is to be run. While a CRON-like format is used, the control of WeeWX report generation using the report_timing option is confined completely to WeeWX and has no interraction with the system CRON service.

The report_timing option consists of five parameters separated by white-space:

report_timing = minutes hours day_of_month months day_of_week

The report_timing parameters are summarised in the following table:

Parameter

Function

Allowable values

minutes

Specifies the minutes of the hour when the report will be run

\*, or  
numbers in the range 0..59 inclusive

hours

Specifies the hours of the day when the report will be run

\*, or  
numbers in the range 0..23 inclusive

day_of_month

Specifies the days of the month when the report will be run

\*, or  
numbers in the range 1..31 inclusive

months

Specifies the months of the year when the report will be run

\*, or  
numbers in the range 1..12 inclusive, or  
abbreviated names in the range jan..dec inclusive

day_of_week

Specifies the days of the week when the report will be run

\*, or  
numbers in the range 0..7 inclusive (0,7 = Sunday, 1 = Monday etc), or  
abbreviated names in the range sun..sat inclusive

The report_timing option may only be used in `weewx.conf`. When set in the [StdReport] section of `weewx.conf` the option will apply to all reports listed under [StdReport]. When specified within a report section, the option will override any setting in [StdReport] for that report. In this manner it is possible to have different reports run at different times. The following sample `weewx.conf` excerpt illustrates this:

[StdReport]

    # Where the skins reside, relative to WEEWX_ROOT
    SKIN_ROOT = skins

    # Where the generated reports should go, relative to WEEWX_ROOT
    HTML_ROOT = public_html

    # The database binding indicates which data should be used in reports.
    data_binding = wx_binding

    # Report timing parameter
    report_timing = 0 \* \* \* \*

    # Each of the following subsections defines a report that will be run.

    [[AReport]]
        skin = SomeSkin

    [[AnotherReport]]
        skin = SomeOtherSkin
        report_timing = \*/10 \* \* \* \*

In this case, the [[AReport]] report would be run under under control of the 0 \* \* \* \* setting (on the hour) under [StdReport] and the [[AnotherReport]] report would be run under control of the \*/10 \* \* \* \* setting (every 10 minutes) which has overriden the [StdReport] setting.

### How report_timing controls reporting

The syntax and interpretation of the report_timing parameters are largely the same as those of the CRON service in many Unix and Unix-like operating systems. The syntax and interpretation are outlined below.

When the report_timing option is in use WeeWX will run a report when the minute, hour and month of year parameters match the report time, and at least one of the two day parameters (day of month or day of week) match the report time. This means that non-existent times, such as "missing hours" during daylight savings changeover, will never match, causing reports scheduled during the "missing times" not to be run. Similarly, times that occur more than once (again, during daylight savings changeover) will cause matching reports to be run more than once.

**Note**  
Report time does not refer to the time at which the report is run, but rather the date and time of the latest data the report is based upon. If you like, it is the effective date and time of the report. For normal WeeWX operation, the report time aligns with the dateTime of the most recent archive record. When reports are run using the wee_reports utility, the report time is either the dateTime of the most recent archive record (the default) or the optional timestamp command line argument.

**Note**  
The day a report is to be run can be specified by two parameters; day of month and/or day of week. If both parameters are restricted (i.e., not an asterisk), the report will be run when either field matches the current time. For example,  
report_timing = 30 4 1,15 \* 5  
would cause the report to be run at 4:30am on the 1st and 15th of each month as well as 4:30am every Friday.

### The relationship between report_timing and archive period

A traditional CRON service has a resolution of one minute, meaning that the CRON service checks each minute as to whether to execute any commands. On the other hand, the WeeWX report system checks which reports are to be run once per archive period, where the archive period may be one minute, five minutes, or some other user defined period. Consequently, the report_timing option may specify a report to be run at some time that does not align with the WeeWX archive period. In such cases the report_timing option does not cause a report to be run outside of the normal WeeWX report cycle, rather it will cause the report to be run during the next report cycle. At the start of each report cycle, and provided a report_timing option is set, WeeWX will check each minute boundary from the current report time back until the report time of the previous report cycle. If a match is found on **any** of these one minute boundaries the report will be run during the report cycle. This may be best described through some examples:

report_timing

Archive period

When the report will be run

0 \* \* \* \*

5 minutes

The report will be run only during the report cycle commencing on the hour.

5 \* \* \* \*

5 minutes

The report will be run only during the report cycle commencing at 5 minutes past the hour.

3 \* \* \* \*

5 minutes

The report will be run only during the report cycle commencing at 5 minutes past the hour.

10 \* \* \* \*

15 minutes

The report will be run only during the report cycle commencing at 15 minutes past the hour

10,40 \* \* \* \*

15 minutes

The report will be run only during the report cycles commencing at 15 minutes past the hour and 45 minutes past the hour.

5,10 \* \* \* \*

15 minutes

The report will be run once only during the report cycle commencing at 15 minutes past the hour.

### Lists, ranges and steps

The report_timing option supports lists, ranges, and steps for all parameters. Lists, ranges, and steps may be used as follows:

*   _Lists_. A list is a set of numbers (or ranges) separated by commas, for example 1, 2, 5, 9 or 0-4, 8-12. A match with any of the elements of the list will result in a match for that particular parameter. If the examples were applied to the minutes parameter, and subject to other parameters in the report_timing option, the report would be run at minutes 1, 2, 5, and 9 and 0, 1, 2, 3, 4, 8, 9, 10, 11, and 12 respectively. Abbreviated month and day names cannot be used in a list.
*   _Ranges_. Ranges are two numbers separated with a hyphen, for example 8-11. The specified range is inclusive. A match with any of the values included in the range will result in a match for that particular parameter. If the example was applied to the hours parameter, and subject to other parameters in the report_timing option, the report would be run at hours 8, 9, 10, and 11. A range may be included as an element of a list. Abbreviated month and day names cannot be used in a range.
*   _Steps_. A step can be used in conjunction with a range or asterisk and are denoted by a '/' followed by a number. Following a range with a step specifies skips of the step number's value through the range. For example, 0-12/2 used in the hours parameter would, subject to other parameter in the report_timing option, run the report at hours 0, 2, 4, 6, 8, and 12. Steps are also permitted after an asterisk in which case the skips of the step number's value occur through the all possible values of the parameter. For example, \*/3 can be used in the hours parameter to, subject to other parameter in the report_timing option, run the report at hours 0, 3, 6, 9, 12, 15, 18, and 21.

### Nicknames

The report_timing option supports a number of time specification 'nicknames'. These nicknames are prefixed by the '@' character and replace the five parameters in the report_timing option. The nicknames supported are:

Nickname

Equivalent setting

When the report will be run

@yearly  
@annually

0 0 1 1 \*

Once per year at midnight on 1 January.

@monthly

0 0 1 \* \*

Monthly at midnight on the 1st of the month.

@weekly

0 0 \* \* 0

Every week at midnight on Sunday.

@daily

0 0 \* \* \*

Every day at midnight.

@hourly

0 \* \* \* \*

Every hour on the hour.

### Examples of report_timing

Numeric settings for report_timing can be at times difficult to understand due to the complex combinations of parameters. The following table shows a number of example report_timing options and the corresponding times when the report would be run.

report_timing

When the report will be run

\* \* \* \* \*

Every archive period. This setting is effectively the default WeeWX method of operation.

25 \* \* \* \*

25 minutes past every hour.

0 \* \* \* \*

Every hour on the hour.

5 0 \* \* \*

00:05 daily.

25 16 \* \* \*

16:25 daily.

25 16 1 \* \*

16:25 on the 1st of each month.

25 16 1 2 \*

16:25 on the 1st of February.

25 16 \* \* 0

16:25 each Sunday.

\*/10 \* \* \* \*

On the hour and 10, 20, 30, 40 and 50 mnutes past the hour.

\*/9 \* \* \* \*

On the hour and 9, 18, 27, 36, 45 and 54 minutes past the hour.

\*/10 \*/2 \* \* \*

0, 10, 20, 30, 40 and 50 minutes after the even hour.

\* 6-17 \* \* \*

Every archive period from 06:00 (inclusive) up until, but excluding, 18:00.

\* 1,4,14 \* \* \*

Every archive period in the hour starting 01:00 to 01:59, 04:00 to 04:59 amd 14:00 to 14:59 (Note excludes report times at 02:00, 05:00 and 15:00).

0 \* 1 \* 0,3

On the hour on the first of the month and on the hour every Sunday and Wednesday.

\* \* 21,1-10/3 6 \*

Every archive period on the 1st, 4th, 7th, 10th and 21st of June.

@monthly

Midnight on the 1st of the month.

### The wee_reports utility and the report_timing option

The report_timing option is ignored when using the [wee_reports](#wee_reports) utility.