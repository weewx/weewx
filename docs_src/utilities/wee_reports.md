# wee_reports

In normal operation, WeeWX generates reports at each archive interval, when
new data arrive. The reports utility is used to generate reports on demand.
It uses the same configuration file that `weewxd` uses.

Specify `--help` to see how it is used:
```
wee_reports --help
```
```
usage: wee_reports --help
       wee_reports [CONFIG_FILE | --config=CONFIG_FILE]
       wee_reports [CONFIG_FILE | --config=CONFIG_FILE] --epoch=TIMESTAMP
       wee_reports [CONFIG_FILE | --config=CONFIG_FILE] --date=YYYY-MM-DD --time=HH:MM

Run all reports defined in the specified configuration file. Use this utility
to run reports immediately instead of waiting for the end of an archive
interval.

positional arguments:
  CONFIG_FILE

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG_FILE  Use the configuration file CONFIG_FILE
  --epoch EPOCH_TIME    Time of the report in unix epoch time
  --date YYYY-MM-DD     Date for the report
  --time HH:MM          Time of day for the report

Specify either the positional argument CONFIG_FILE, or the optional argument
--config, but not both.
```

By default, the reports are generated as of the last timestamp in the database,
however, an explicit time can be given by using either option `--epoch`, or by
using options `--date` and `--time`.

### `--config`

An optional path to the configuration file (usually, `weewx.conf`) can be given
as either a positional argument, or by using option `--config` (but not both).
If not given, the location of the configuration file will be inferred.

### `--epoch`

Generate the reports so that they are current as of the given unix epoch time.

```
wee_reports --epoch=1652367600
```

This would generate a report for unix epoch time 1652367600 (12-May-2022 at
8AM PDT).

### `--date`
### `--time`

Generate the reports so that they are current as of the given date
and time. The date should be given in the form `YYYY-MM-DD` and the time should
be given as `HH:DD`.

```
wee_reports /home/weewx/weewx.conf --date=2022-05-12 --time=08:00
```

This would generate a report for 12-May-2022 at 8AM (unix epoch time
1652367600).
