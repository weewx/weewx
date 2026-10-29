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
  --updateagg           Aggregate imported readings into existing archive intervals.
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

### `--updateagg`

`--updateagg` combines imported readings for each existing archive interval,
then updates the mapped observations in that row. For example, six temperature
readings within a five-minute archive interval become one average. Rainfall
amounts are summed instead. The archive row's timestamp, unit system, interval
and unmapped observations stay unchanged. Missing target rows are never inserted.
This option cannot be combined with `--update`.

Preview the results before applying them:

```sh
weectl import --import-config=/directory/import.conf --updateagg --dry-run
```

The preview shows the old and proposed values for the first 20 target rows,
with counts for all target rows, unmatched readings, readings outside the date
limits and duplicate timestamps. All import periods are checked before any
updates are written. Running without `--dry-run` asks for confirmation after
the preview; `--no-prompt` accepts it. Updates use the usual database batches,
so a write failure can leave earlier batches committed.

#### Choosing archive intervals

By default a reading belongs to the archive interval that contains its time.
An archive row at 12:05 with `interval = 5` covers times after 12:00 through
12:05, including 12:05. Each row's stored interval is used, including when
intervals vary or cross midnight or a daylight saving transition. The import
source's `interval` setting is ignored in this mode.

Readings in gaps are counted as unmatched and skipped. Overlapping archive
intervals stop the import before updates are written. If an earlier import
created extra archive rows, an `anchor` can restrict the target rows to those
with a non-NULL value in a chosen observation, such as `outTemp`. The extra
rows are not removed by this option.

To match labels that differ slightly from the intended archive timestamp, add
`[[UpdateAggregation]]` inside the source section of the import configuration:

```ini
[CSV]
    # Other CSV settings and FieldMap go here.
    [[UpdateAggregation]]
        alignment = nearest
        max_shift = 15
        anchor = outTemp
```

For example, a reading stamped 12:05:06 can then update the 12:05 archive row.
The archive must contain that target row, and `outTemp` must be non-NULL there.

| Setting | Values and default |
|---------|--------------------|
| `alignment` | `interval` (default), `nearest`, `previous` or `next`. The latter three match an archive timestamp rather than the interval it ends. `previous` and `next` include an exact match. |
| `max_shift` | Maximum distance in seconds between reading and target timestamps. Must be finite and non-negative. Required for `nearest`, `previous` and `next`; omitted by default for `interval`. Readings beyond it are unmatched. |
| `anchor` | An archive column whose value must be non-NULL in each target row. Default is to consider every archive row. |

An equally close pair of target timestamps stops `nearest` alignment before
updates are written. The `--date`, `--from` and `--to` filters apply to source
readings and to target timestamps: an update cannot cross the selected date
limits. As with other imports, the beginning is exclusive and the end inclusive.

#### Choosing how observations are combined

Aggregation uses the WeeWX
[accumulator settings](../reference/weewx-options/accumulator.md) in
`weewx.conf`. The standard observation types have defaults: temperature and
pressure are averaged, rain and ET are summed, and running counters such as
`dayRain` use the last reading. Averages give each non-missing sample equal
weight; the spacing between readings does not change that weight. Input
conversion and quality control take place before aggregation.

Every custom observation must have an explicit `extractor` in `[Accumulator]`,
even when its units have been registered. For a cumulative energy meter whose
reading should be kept at the end of an interval, add to `weewx.conf`:

```ini
[Accumulator]
    [[energyprod]]
        extractor = last
```

Use `avg` for instantaneous power readings or `sum` for separate amounts
produced during each source interval. The field must exist in the archive
schema and have the usual import unit mapping. The accumulator reference
lists the other extractors and how to configure text fields.

Wind uses WeeWX's vector and gust handling. Map `windSpeed` together with
`windDir`, `windGust` or `windGustDir`. Only mapped fields are updated, even
when the wind accumulator computes additional fields.

Missing values, including empty text, do not clear existing observations.
A field with no non-missing inputs keeps its stored value; zero is a value.
Duplicate source timestamps retain the first reading, including across import
periods. `first` and `last` follow timestamp order. Non-finite inputs or
aggregates stop the import before updates are written. Derived observations
are not calculated in this mode, and import `lastUpdate` metadata is unchanged.

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
