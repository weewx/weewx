Before starting, it's worth running the utility with the `--help` flag to see
how `weectl import` is used:

```
weectl import --help
```
```
usage: weectl import --help
       weectl import --import-config=IMPORT_CONFIG_FILE
                     [--config=CONFIG_FILE]
                     [[--date=YYYY-mm-dd] | [[--from=YYYY-mm-dd[THH:MM]] [--to=YYYY-mm-dd[THH:MM]]]]
                     [--dry-run][--verbose]
                     [--no-prompt][--suppress-warnings]

Import observation data into a WeeWX archive.

optional arguments:
  -h, --help            show this help message and exit
  --config FILENAME     Path to configuration file.
  --import-config IMPORT_CONFIG_FILE
                        Path to import configuration file.
  --dry-run             Print what would happen but do not do it.
  --date YYYY-mm-dd     Import data for this date. Format is YYYY-mm-dd.
  --from YYYY-mm-dd[THH:MM]
                        Import data starting at this date or date-time. Format is YYYY-
                        mm-dd[THH:MM].
  --to YYYY-mm-dd[THH:MM]
                        Import data up until this date or date-time. Format is YYYY-mm-
                        dd[THH:MM].
  --verbose             Print and log useful extra output.
  --no-prompt           Do not prompt. Accept relevant defaults and all y/n prompts.
  --suppress-warnings   Suppress warnings to stdout. Warnings are still logged.

Import data from an external source into a WeeWX archive. Daily summaries are updated as
each archive record is imported so there should be no need to separately rebuild the
daily summaries.
```

## Options

### `--config=FILENAME`


The utility can usually guess where the configuration file is,
but if you have an unusual installation or multiple stations, you may have to
tell it explicitly.

```
weectl import --config=/this/directory/weewx.conf --import-config=/directory/import.conf
```

### `--import-config=FILENAME`

`weectl import` uses a secondary configuration file, known as the import
configuration file, to store various import parameters. The `--import-config`
option is mandatory for all imports. Example import configuration files for
each type of import supported by `weectl import` are provided in the
`util/import` directory. These example files are best used by making a copy of
into a working directory and then modifying the copy to suit your needs. The
`--import-config` option is used as follows:

```
weectl import --import-config=/directory/import.conf
```

### `--dry-run`

The `--dry-run` option will cause the import to proceed but no actual data 
will be saved to the database. This is a useful option to use when first 
importing data.

```
weectl import --import-config=/directory/import.conf --dry-run
```

### `--date=YYYY-mm-dd`

Records from a single date can be imported by use of the `--date` option. 
The `--date` option accepts strings of the format `YYYY-mm-dd`. Whilst the 
use of the `--date` option will limit the imported data to that of a single 
date, the default action if the `--date` option (and the `--from` and `--to` 
options) is omitted may vary depending on the source. The operation of the 
`--date` option is summarised in the following table:

<table>
  <caption>Option <span class="code">--date</span></caption>
  <tbody>
    <tr class="first_row">
      <td>option</td>
      <td>Records imported for a CSV, Cumulus, Weather Display or WeatherCat 
import</td>
      <td>Records imported for a Weather Underground import</td>
    </tr>
    <tr>
      <td class="code first_col">omitted<br>(i.e., the default)</td>
      <td>All available records</td>
      <td>Today's records only</td>
    </tr>
    <tr>
      <td class="code first_col">--date=2015-12-22</td>
      <td>All records from 2015-12-22 00:00 (exclusive) to 2015-12-23 00:00 
(inclusive)</td>
      <td>All records from 2015-12-22 00:00 (exclusive) to 2015-12-23 00:00 
(inclusive)</td>
    </tr>
  </tbody>
</table>

!!! Note
    If the `--date`, `--from` and `--to` options are omitted the default is to
    import today's records only when importing from Weather Underground or to
    import all available records when importing from any other source.

!!! Note
    WeeWX considers an archive record to represent an aggregation of data over
    the archive interval preceding the archive record's timestamp. For this
    reason imports which are to be limited to a given date with the `--date`
    option will only import records timestamped after midnight at the start
    of the day concerned and up to and including midnight at the end of the
    day concerned.

### `--from` and `--to`

Whilst the `--date` option allows imported data to be limited to a single 
date, the `--from` and `--to` options allow finer control by importing 
only the records that fall within the date or date-time range specified by 
the `--from` and `--to` options. The `--from` option determines the 
earliest (inclusive), and the `--to` option determines the latest 
(exclusive), date or date-time of the records being imported. The `--from` 
and `--to` options accept a string of the format `YYYY-mm-dd[THH:MM]`. The 
T literal is mandatory if specifying a date-time.

!!! Note
    The `--from` and `--to` options must be used as a pair, they cannot be
    used individually or in conjunction with the `--date`option.

The operation of the `--from` and `--to` options is summarised in the 
following table:

<table>
  <caption>Options <span class="code">--from</span> and <span 
class="code">--to</span></caption>
  <tbody>
    <tr class="first_row">
      <td colspan='2'>options</td>
      <td>Records imported for a CSV, Cumulus, Weather Display or WeatherCat 
import</td>
      <td>Records imported for a Weather Underground import</td>
    </tr>
    <tr>
      <td class="code first_col">omitted<br>(i.e., the default)</td>
      <td class="code first_col">omitted<br>(i.e., the default)</td>
      <td>All available records</td>
      <td>Today's records only</td>
    </tr>
    <tr>
      <td class="code first_col">--from=2015-12-22</td>
      <td class="code first_col">--to=2015-12-29</td>
      <td>All records from 2015-12-22 00:00 (exclusive) to 2015-12-30 00:00 
(inclusive)</td>
      <td>All records from 2015-12-22 00:00 (exclusive) to 2015-12-30 00:00 
(inclusive)</td>
    </tr>
    <tr>
      <td class="code first_col">--from=2016-7-18T15:29</td>
      <td class="code first_col">--to=2016-7-25</td>
      <td>All records from 2016-7-18 15:29 (exclusive) to 2016-7-26 00:00 
(inclusive)</td>
      <td>All records from 2016-7-18 15:29 (exclusive) to 2016-7-26 00:00 
(inclusive)</td>
    </tr>
    <tr>
      <td class="code first_col">--from=2016-5-12</td>
      <td class="code first_col">--to=2016-7-22T22:15</td>
      <td>All records from 2016-5-12 00:00 (exclusive) to 2016-7-22 22:15 
(inclusive)</td>
      <td>All records from 2016-5-12 00:00 (exclusive) to 2016-7-22 22:15 
(inclusive)</td>
    </tr>
    <tr>
      <td class="code first_col">--from=2016-3-18T15:29</td>
      <td class="code first_col">--to=2016-6-20T22:00</td>
      <td>All records from 2016-3-18 15:29 (exclusive) to 2016-6-20 22:00 
(inclusive)</td>
      <td>All records from 2016-3-18 15:29 (exclusive) to 2016-6-20 22:00 
(inclusive)</td>
    </tr>
  </tbody>
</table>

!!! Note
    If the `--date`, `--from` and `--to` options are omitted the default is
    to import today's records only when importing from Weather Underground or
    to import all available records when importing from any other source.

!!! Note
    WeeWX considers an archive record to represent an aggregation of data over
    the archive interval preceding the archive record's timestamp. For this
    reason imports which are to be limited to a given timespan with the
    `--from` and `--to` options will only import records timestamped after
    the timestamp represented by the `--from` option and up to and including
    the timestamp represented by the `--to` option.

### `--verbose`

Inclusion of the `--verbose` option will cause additional information to be
printed during `weectl import` execution.

```
weectl import --import-config=/directory/import.conf --verbose
```

### `--no-prompt`

Inclusion of the `--no-prompt` option will run `weectl import` without prompts.
Relevant defaults will be used and all y/n prompts are automatically accepted
as 'y'. This may be useful for unattended use of `weectl import`.

```
weectl import --import-config=/directory/import.conf --no-prompt
```

!!! Warning
    Care must be taken when using the `--no-prompt` option as ignoring 
    warnings during the import process can lead to unexpected results. Whilst 
    existing data will be protected, the use or acceptance of an 
    incorrect or unexpected parameter or default may lead to significant 
    amounts of unwanted data being imported.

### `--suppress-warnings`

The `--suppress-warnings` option suppresses `weectl import` warning messages from
being displayed on the console during the import. `weectl import` may issue a
number of warnings during import. These warnings may be due to the source
containing more than one entry for a given timestamp or there being no data
found for a mapped import field. These warnings do not necessarily require
action, but they can consist of extensive output and thus make it difficult
to follow the import progress. Irrespective of whether `--suppress-warnings`
is used all warnings are sent to log.

```
weectl import --import-config=/directory/import.conf --suppress-warnings
```
