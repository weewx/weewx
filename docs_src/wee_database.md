# wee_database

The database utility simplifies typical database maintenance operations. For
example, it can rebuild the daily summaries or check a SQLite database for
embedded strings where floats are expected.

Run the utility with the `--help` option to see how it is used:
```shell
wee_database --help
Usage: wee_database --help
       wee_database --create
       wee_database --reconfigure
       wee_database --transfer --dest-binding=BINDING_NAME [--dry-run]
       wee_database --add-column=NAME [--type=(REAL|INTEGER)]
       wee_database --rename-column=NAME --to-name=NEW_NAME
       wee_database --drop-columns=NAME1,NAME2,...
       wee_database --check
       wee_database --update [--dry-run]
       wee_database --drop-daily
       wee_database --rebuild-daily [--date=YYYY-mm-dd |
                                    [--from=YYYY-mm-dd] [--to=YYYY-mm-dd]]
                                    [--dry-run]
       wee_database --reweight [--date=YYYY-mm-dd |
                               [--from=YYYY-mm-dd] [--to=YYYY-mm-dd]]
                               [--dry-run]
       wee_database --calc-missing [--date=YYYY-mm-dd |
                                   [--from=YYYY-mm-dd[THH:MM]] [--to=YYYY-mm-dd[THH:MM]]]
       wee_database --check-strings
       wee_database --fix-strings [--dry-run]

Description:

Manipulate the WeeWX database. Most of these operations are handled
automatically by WeeWX, but they may be useful in special cases.

Options:
  -h, --help            show this help message and exit
  --create              Create the WeeWX database and initialize it with the
                        schema.
  --reconfigure         Create a new database using configuration information
                        found in the configuration file. The new database will
                        have the same name as the old database, with a '_new'
                        on the end.
  --transfer            Transfer the WeeWX archive from source database to
                        destination database.
  --add-column=NAME     Add new column NAME to database.
  --type=TYPE           New database column type (INTEGER|REAL) (option --add-
                        column only).  Default is 'REAL'.
  --rename-column=NAME  Rename the column with name NAME.
  --to-name=NEW_NAME    New name of the column (option --rename-column only).
  --drop-columns=NAME1,NAME2,...
                        Drop one or more columns. Names must be separated by
                        commas, with NO SPACES.
  --check               Check the calculations in the daily summary tables.
  --update              Update the daily summary tables if required and
                        recalculate the daily summary maximum windSpeed
                        values.
  --calc-missing        Calculate and store any missing derived observations.
  --check-strings       Check the archive table for null strings that may have
                        been introduced by a SQL editing program.
  --fix-strings         Fix any null strings in a SQLite database.
  --drop-daily          Drop the daily summary tables from a database.
  --rebuild-daily       Rebuild the daily summaries from data in the archive
                        table.
  --reweight            Recalculate the weighted sums in the daily summaries.
  --config=CONFIG_FILE  Use configuration file CONFIG_FILE.
  --date=YYYY-mm-dd     This date only (options --calc-missing and --rebuild-
                        daily only).
  --from=YYYY-mm-dd[THH:MM]
                        Start with this date or date-time (options --calc-
                        missing and --rebuild-daily only).
  --to=YYYY-mm-dd[THH:MM]
                        End with this date or date-time (options --calc-
                        missing and --rebuild-daily only).
  --binding=BINDING_NAME
                        The data binding to use. Default is 'wx_binding'.
  --dest-binding=BINDING_NAME
                        The destination data binding (option --transfer only).
  --dry-run             Print what would happen but do not do it. Default is
                        False.
```

## Actions and options

### create

If the database does not already exist, this action will create it and
initialize it with the schema specified in the WeeWX configuration file.
Because WeeWX does this automatically, this action is rarely needed.

```shell
wee_database --create
```

### reconfigure

This action is useful for changing the schema or unit system in your database.

It creates a new database with the same name as the old, except with the suffix
`_new` attached at the end (nominally, `weewx.sdb_new` if you are using SQLite,
`weewx_new` if you are using MySQL). It then initializes it with the schema
specified in `weewx.conf`. Finally, it copies over the data from your old
database into the new database.

```shell
wee_database --reconfigure
```

See the section <a href="customizing.htm#Changing_the_unit_system">Changing
the database unit system in an existing database</a> in the Customization
Guide for step-by-step instructions that use this option.

### transfer

This action is useful for moving your database from one type of database to
another, such as from SQLite to MySQL. To use it, you must have two bindings
specified in your `weewx.conf` configuration file. One will serve as the
source, the other as the destination. Specify the source binding with option
`--binding`, the destination binding with option `--dest-binding`. The
`--binding` option may be omitted in which case the default `wx-binding`
will be used.


```shell
wee_database --transfer --binding=source_binding --dest-binding=dest_binding
wee_database --transfer --dest-binding=dest_binding
```

See the Wiki for examples of moving data from <a href="https://github.com/weewx/weewx/wiki/Transfer%20from%20sqlite%20to%20MySQL#using-wee_database">SQLite to MySQL</a>, and from <a href="https://github.com/weewx/weewx/wiki/Transfer%20from%20MySQL%20to%20sqlite#using-wee_database">MySQL to SQLite</a>, using `wee_database`.

### add-column

This action adds a new database observation type (column) to the database. If
used without the `--type` option, the type will default to `REAL`.

```shell
wee_database --add-column
```

Optionally, option `--type` can be used with a SQL type `REAL`, `INTEGER`,
or any other SQL column definition (such as `INTEGER DEFAULT 0`).

```shell
wee_database --add-column=NAME --type=TYPE
```

### rename-column

Use this action to rename a database observation type (column) to a new name.
It requires the option `--to-name`.

```shell
wee_database --rename-column=NAME --to-name=NEW_NAME
```

For example, to rename the column `luminosity` in your schema to `illuminance`:

```shell
wee_database --rename-column=luminosity --to-name=illuminance
```

### drop-columns

This action will drop one or more observation types (columns) from the
database. If more than one column name is given, they should be separated by
commas and <em>no spaces</em>.

It is an error to attempt to drop a non-existing column. In this case, nothing
will be done.

```shell
wee_database --drop-columns=NAME1,NAME2
```

!!! Note
    When dropping columns from a SQLite database, the entire database must be
    copied except for the dropped columns. Because this can be quite slow, if
    you are dropping more than one column, it is better to do them all in one
    pass. This is why option `--drop-columns` accepts more than one name.


### check

This action will check the calculations in the daily summary tables as well as
checking the archive for null strings (refer to `--check-strings`). If the
daily summary tables contain summaries calculated using an old algorithm, the
user is advised to update the daily summary tables using the `--update` action.
If null strings are found the user is advised to fix them using the
`--fix-strings` action.

```shell
wee_database --check
```

<a id="wee_database_utility_update">FIXME</a>

### update

This action updates the daily summary tables to use interval weighted
calculations as well as recalculating the `windSpeed` maximum daily values and
times. Interval weighted calculations are only applied to the daily summaries
if not previously applied. The update process is irreversible and users are
advised to backup their database before performing this action.

```shell
wee_database --update
```

For further information on interval weighting and recalculation of daily
`windSpeed` maximum values, see the sections <a href="upgrading.htm#change_to_daily_summaries">Changes to daily summaries</a> and <a href="upgrading.htm#recalculation_of_windspeed">Recalculation of `windSpeed` maximum values</a> in the Upgrade Guide.


### drop-daily

In addition to the regular archive data, every WeeWX database also includes a
daily summary table for each observation type. Because there can be dozens of
observation types, there can be dozens of these daily summaries. It does not
happen very often, but there can be occasions when it's necessary to drop them
all and then rebuild them. Dropping them by hand would be very tedious! This
action does them all at once.

```shell
wee_database --drop-daily
```

### rebuild-daily

This action is the inverse of action `--drop-daily` in that it rebuilds the
daily summaries from the archive data. In most cases it is not necessary to
drop the daily summary tables using the action `--drop-daily` before rebuilding
them.

The action `--rebuild-daily` accepts a number of date related options,
`--date`, `--from` and `--to` that allow selective rebuilding of the daily
summaries for one or more days rather than for the entire archive history.
These options may be useful if bogus data has been removed from the archive
covering a single day or a period of few days. The daily summaries can then
be rebuilt for this period only, resulting in a faster rebuild and detailed
low/high values and the associated times being retained for unaffected days.

The `--date` option limits the daily summary rebuild to the specified date.

The `--from` and `--to` options may be used together or individually to limit
the daily summary rebuild to a specified period. When used individually the
`--to` option limits the rebuild to the inclusive period from the earliest date
for which there is data in the database through to and including the specified
date. Similarly when used individually the `--from` option limits the rebuild
to the inclusive period from the specified date through until the last date
for which there is data in the database. When the `--from` and `--to` options
are used together the daily summary rebuild is limited to the specified
inclusive period.

```shell
wee_database --rebuild-daily
wee_database --rebuild-daily --date=YYYY-mm-dd
wee_database --rebuild-daily --from=YYYY-mm-dd
wee_database --rebuild-daily --to=YYYY-mm-dd
wee_database --rebuild-daily --from=YYYY-mm-dd --to=YYYY-mm-dd
```

!!! Note
    Whilst the `--from` and `--to` options will accept optional hour and
    minutes in the format `THH:MM`, any such hour and minute options are
    ignored by the `--rebuild` action as the daily summaries represent whole
    days only and it is not possible to partially rebuild a daily summary.

!!! Note
    When used with the `--rebuild-daily` action the period defined by `--to`
    and `--from` is inclusive and the daily summary tables will be rebuild for
    the day defined by `--from` and the day defined by `--to` and all days in
    between.


### reweight

As an alternative to dropping and rebuilding the daily summaries, this action
simply rebuilds the weighted daily sums (used to calculate averages) from the
archive data. It does not touch the highs and lows. It is much faster than
`--rebuild-daily`, and has the advantage that the highs and lows remain
unchanged.

Other options are as in `--rebuild-daily`.


### calc-missing

This action calculates derived observations for archive records in the database and then stores the calculated
observations in the database. This can be useful if erroneous archive data is corrected or some additional
observational data is added to the archive that may alter previously calculated or missing derived
observations.

The period over which the derived observations are calculated can be limited through use of the
`--date`, `--from` and/or `--to`
options. When used without any of these options `--calc-missing` will calculate
derived observations for all archive records in the database. The `--date` option
limits the calculation of derived observations to the specified date only. The `--from`
and `--to` options can be used together to specify the start and end date-time
respectively of the period over which derived observations will be calculated. If `--from`
is used by itself the period is fom the date-time specified up to and including the last archive record in
the database. If `--to` is used by itself the period is the first archive record in
the database through to the specified date-time.

```shell
wee_database --calc-missing
wee_database --calc-missing --date=YYYY-mm-dd
wee_database --calc-missing --from=YYYY-mm-dd[THH:MM]
wee_database --calc-missing --to=YYYY-mm-dd[THH:MM]
wee_database --calc-missing --from=YYYY-mm-dd[THH:MM] --to=YYYY-mm-dd[THH:MM]
```

!!! Note
    When a `YYYY-mm-dd` date is used as the `--from` option the period used by
    `--calc-missing` includes records after midnight at the start of
    `YYYY-mm-dd`, if a `YYYY-mm-ddTHH:MM` format date-time is used as the
    `--from` option the period includes records after `YYYY-mm-dd HH:MM`.
    When a `YYYY-mm-dd` date is used as the `--to` option the period includes
    records up to and including midnight at the end of `YYYY-mm-dd`, if a
    `YYYY-mm-ddTHH:MM` format date-time is used as the `--to` option the period
    includes records up to and including `YYYY-mm-dd HH:MM`. When using the
    `--date` option the period is all records after midnight at the start of
    `YYYY-mm-dd` up to and including midnight at the end of `YYYY-mm-dd`, in
    effect the same as `--from=YYYY-mm-ddT00:00 --to=YYYY-mm-dd+1T00:00`.

!!! Note
    `--calc-missing` uses the `StdWXCalculate` service to calculate missing
    derived observations. The data binding used by the `StdWXCalculate` service
    should normally match the data binding of the database being operated on by
    `--calc-missing`. Those who use custom or additional data bindings should
    take care to ensure the correct data bindings are used by both
    `--calc-missing` and the `StdWXCalculate` service. Those who use the
    default data binding need take no special precautions.


<a id="wee_database_utility_check_strings">FIXME</a>

### check-strings

Normally, all entries in the archive are numbers. However, some SQLite
database editors use a null string instead of a null value when deleting
entries. These null strings can cause problems. This action checks the
database to see if it contains any null strings.

```shell
wee_database --check-strings
```

### fix-strings

This action will check for any null strings in a SQLite database and if found
substitute a true null value.

```shell
wee_database --fix-strings
```
