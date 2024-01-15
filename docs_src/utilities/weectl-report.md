# weectl report

Use the `weectl` subcommand `report` to run and list reports.

Specify `--help` to see the actions and options.

## List reports

    weectl report list
        [--config=FILENAME]

The `list` action will list all the reports in the configuration file, along
with which skin they use, and other information. For example:

```
$ weectl report list
Using configuration file /Users/ted_user/weewx-data/weewx.conf

              Report  Skin         Enabled   Units   Language
       SeasonsReport  Seasons         Y        US       EN   
    SmartphoneReport  Smartphone      N        US       EN   
        MobileReport  Mobile          N        US       EN   
      StandardReport  Standard        N        US       EN   
                 FTP  Ftp             N        US       EN   
               RSYNC  Rsync           N        US       EN   
```

## Run reports on demand

    weectl report run [NAME ...]
        [--config=FILENAME]
        [--epoch=EPOCH_TIME | --date=YYYY-mm-dd --time=HH:MM] 

In normal operation, WeeWX generates reports at each archive interval after new
data has arrived. The action `weectl report run` is used to generate reports on
demand. It uses the same configuration file that `weewxd` uses.

The names of the reports to be run can be given on the command line, separated
by spaces. It does not matter whether the report has been enabled or not: it
will be run. Note: names are _case sensitive!_ Use `weectl report list` to 
determine the names. 

For example, to run the reports `MobileReport` and `SmartphoneReport`:

    weectl report run MobileReport SmartphoneReport

If no report names are given, then all enabled reports will be run:

    # Run all enabled reports:    
    weectl report run

By default, the reports are generated as of the last timestamp in the database,
however, an explicit time can be given by using either option `--epoch`, or by
using options `--date` and `--time` together.

For example, to specify an explicit unix epoch time, use option `--epoch`:

```
weectl report run --epoch=1652367600
```

This would generate a report for unix epoch time 1652367600 (12-May-2022 at
8AM PDT).

Alternatively, you can specify a date and time, by using options `--date` and
`--time`:

```
weectl report run --date=2022-05-12 --time=08:00
```

This would generate a report for 12-May-2022 at 8AM (unix epoch time
1652367600).

## Options

These are options used by most of the actions.

### --config

Path to the configuration file. Default is `~/weewx-data/weewx.conf`.

### --date=YYYY-mm-dd and --time=HH:MM

Generate the reports so that they are current as of the given date
and time. The date should be given in the form `YYYY-mm-dd` and the time should
be given as `HH:MM`.

### --epoch=EPOCH_TIME

Generate the reports so that they are current as of the given unix epoch time.

### --help

Show the help message, then exit.
