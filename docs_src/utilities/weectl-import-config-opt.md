`weectl import` requires a second configuration file, the import configuration 
file, in addition to the standard WeeWX configuration file. The import 
configuration file specifies the import type and various options associated 
with the import type. The import configuration file is specified using the 
mandatory `--import-config` option. How you construct the import 
configuration file is up to you; however, the recommended method is to copy 
one of the example import configuration files located in the `util/import` 
directory, modify the configuration options in the newly copied file to suit 
the import to be performed and then use this file as the import configuration 
file.

Following is the definitive guide to the options available in the import 
configuration file. Where a default value is shown this is the value that will 
be used if the option is omitted from the import configuration file.

### `source`{#import_config_source}

The `source` option determines the type of import to be performed by 
`weectl import`. The option is mandatory and must be set to one of the following:

* `CSV` to import from a single CSV format file.
* `WU` to import from a Weather Underground PWS history
* `Cumulus` to import from one or more Cumulus monthly log files.
* `WD` to import from one or more Weather Display monthly log files.
* `WeatherCat` to import from one or more WeatherCat monthly .cat files.

Mandatory, there is no default.

## [CSV]

The `[CSV]` section contains the options controlling the import of 
observational data from a CSV format file.

### `file`{#csv_file}

The file containing the CSV format data to be used as the source during the 
import. Include full path and filename.

Mandatory, there is no default.

### `source_encoding`{#csv_encoding}

The source file encoding. This parameter should only need be 
used if the source file uses an encoding other than UTF-8 or an ASCII 
compatible encoding. If used, the setting used should be a
<a href="https://docs.python.org/3/library/codecs.html#standard-encodings">Python Standard Encoding</a>.

Optional, the default is `utf-8-sig`.

### `delimiter`{#csv_delimiter}

The character used to separate fields. This parameter must be included in 
quotation marks.

Optional, the default is `','` (comma).

### `decimal`{#csv_decimal}

The character used as the decimal point in the source files. A full stop is 
frequently used, but it may be another character. This parameter must be 
included in quotation marks.

Optional, the default is `'.'`.

### `interval`{#csv_interval}

Determines how the time interval (WeeWX archive table field `interval`) 
between successive observations is derived. The interval can be derived by 
one of three methods:

* The interval can be calculated as the time, rounded to the nearest minute, 
  between the date-time of successive records. This method is suitable when 
  the data was recorded at fixed intervals and there are **NO** missing records 
  in the source data. Use of this method when there are missing records in 
  the source data can compromise the integrity of the WeeWX statistical data.
  Select this method by setting `interval = derive`.

* The interval can be set to the same value as the `archive_interval` 
  setting under `[StdArchive]` in `weewx.conf`. This setting is useful if 
  the data was recorded at fixed intervals, but there are some missing 
  records and the fixed interval is the same as the `archive_interval` 
  setting under `[StdArchive]` in `weewx.conf`. Select this method by 
  setting `interval = conf`.

* The interval can be set to a fixed number of minutes. This setting is 
  useful if the source data was recorded at fixed intervals, but there are 
  some missing records and the fixed interval is different to the 
  `archive_interval` setting under `[StdArchive]` in `weewx.conf`. Select 
  this method by setting `interval = x` where `x` is an integer number of 
  minutes.

If the CSV source data records are equally spaced in time, but some 
records are missing, then a better result may be achieved using `conf` or 
a fixed interval setting.

Optional, the default is `derive`. 

### `qc`{#csv_qc}

Determines whether simple quality control checks are applied to imported 
data. Setting `qc = True` will result in `weectl import` applying the WeeWX 
`StdQC` minimum and maximum checks to any imported observations. Setting `qc 
= False` will result in `weectl import` not applying quality control checks 
to imported data. `weectl import` quality control checks use the same 
configuration settings, and operate in the same manner, as the 
[_StdQC_](../reference/weewx-options/stdqc.md) service. For example, for 
minimum/maximum quality checks, if an observation falls outside of the 
quality control range for that observation, the observation will be set to 
`None`. In such cases you will be alerted through a log entry similar to:

```
2023-11-04 16:59:01 weectl-import[3795]: WARNING weewx.qc: 2023-10-05 18:30:00 
AEST (1696494600) Archive value 'outTemp' 194.34 outside limits (0.0, 120.0)
```

!!! Note
    As derived observations are calculated after the quality control check is 
    applied, derived observations are not subject to quality control checks. 

Optional, the default is `True`.

### `calc_missing`{#csv_calc_missing}

Determines whether any missing derived observations will be calculated 
from the imported data. Setting `calc_missing = True` will result in 
`weectl import` using the WeeWX `StdWXCalculate` service to calculate any 
missing derived observations from the imported data. Setting `calc_missing 
= False` will result in WeeWX leaving any missing derived observations as 
`None`. See [_[StdWXCalculate]_](../reference/weewx-options/stdwxcalculate.md) 
for details of the observations the `StdWXCalculate` service can calculate.

Optional, the default is `True`.

### `ignore_invalid_data`{#csv_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import 
aborted. If invalid data is found in a source field and 
`ignore_invalid_data` is `True` the corresponding WeeWX destination field is
set to `None` and the import continues. The import is aborted if 
`ignore_invalid_data` is `False` and invalid data is found in a source field.

Optional, the default is `True`.

### `tranche`{#csv_tranche}

To speed up database operations imported records are committed to database 
in groups of records rather than individually. The size of the group is 
set by the `tranche` parameter. Increasing the `tranche` parameter may 
result in a slight speed increase, but at the expense of increased memory 
usage. Decreasing the `tranche` parameter will result in less memory usage, 
but at the expense of more frequent database access and likely increased 
time to import.

Optional, the default is `250` which should suit most users.

### `UV_sensor`{#csv_UV}

WeeWX records a `None/null` for `UV` when no UV sensor is installed, whereas 
some weather station software records a value of 0 for UV index when there 
is no UV sensor installed. The `UV_sensor` parameter enables `weectl import` 
to distinguish between the case where a UV sensor is present and the UV index 
is 0 and the case where no UV sensor is present and UV index is 0. 
`UV_sensor = False` should be used when no UV sensor was used in producing 
the source data. `UV_sensor = False` will result in `None/null` being recorded
in the WeeWX archive field `UV` irrespective of any UV observations in the 
source data. `UV_sensor = True` should be used when a UV sensor was used 
in producing the source data. `UV_sensor = True` will result in UV 
observations in the source data being stored in the WeeWX archive field `UV`.

Optional, the default is `True`.

### `solar_sensor`{#csv_solar}

WeeWX records a `None/null` when no solar radiation sensor is installed, 
whereas some weather station software records a value of 0 for solar 
radiation when there is no solar radiation sensor installed. The 
`solar_sensor` parameter enables `weectl import` to distinguish between 
the case where a solar radiation sensor is present and solar radiation is 
0 and the case where no solar radiation sensor is present and solar 
radiation is 0. `solar_sensor = False` should be used when no solar 
radiation sensor was used in producing the source data. `solar_sensor = 
False` will result in `None/null` being recorded in the WeeWX archive 
field `radiation` irrespective of any solar radiation observations in the 
source data. `solar_sensor = True` should be used when a solar radiation 
sensor was used in producing the source data. `solar_sensor = True` will 
result in solar radiation observations in the source data being stored in 
the WeeWX archive field `radiation`.

Optional, the default is `True`.

### `raw_datetime_format`{#csv_raw_datetime_format}

WeeWX stores each record with a unique unix epoch timestamp, whereas many 
weather station applications or web sources export observational data with 
a human-readable date-time. This human-readable date-time is interpreted 
according to the format set by the `raw_datetime_format` option. This 
option consists of [Python strptime() format codes](https://docs.python. org/2/library/datetime.html#strftime-and-strptime-behavior) and literal 
characters to represent the date-time data being imported.

For example, if the source data uses the format '23 January 2015 15:34' the 
appropriate setting for `raw_datetime_format` would be `%d %B %Y %H:%M`, 
'9:25:00 12/28/16' would use `%H:%M:%S %m/%d/%y`. If the source data 
provides a unix epoch timestamp as the date-time field the unix epoch 
timestamp is used directly and the `raw_datetime_format` option is ignored.

Optional, the default is `%Y-%m-%d %H:%M:%S`.

!!! Note
    `weectl import` does not support the construction of the unique record 
    date-time stamp from separate date and time fields, rather the date-time 
    information for each imported record must be contained in a single field. 
    CSV data containing separate date and time fields may require further 
    manual processing before it can be imported.

### `wind_direction`{#csv_wind_direction}

WeeWX records wind direction in degrees as a number from 0 to 360 
inclusive (no wind direction is recorded as `None/null`), whereas some 
data sources may provide wind direction as a number over a different range 
(e.g., -180 to +180), or may use a particular value when there is no wind 
direction (e.g., 0 may represent no wind direction and 360 may represent a 
northerly wind, or -9999 (or some similar clearly invalid number of degrees)
to represent there being no wind direction). `weectl import` handles such 
variations in data by defining a range over which imported wind direction 
values are accepted. Any value outside of this range is treated as there 
being no wind direction and is recorded as `None/null`. Any value inside 
the range is normalised to the range 0 to 360 inclusive (e.g., -180 would 
be normalised to 180). The `wind_direction` option consists of two comma 
separated numbers of the format lower, upper where lower and upper are 
inclusive. The operation of the `wind_direction` option is best 
illustrated through the following table:

<table id='wind_direction' style="width:80%;text-align: center">
  <caption>Option wind_direction</caption>
  <tbody>
    <tr class="first_row">
      <td>wind_direction option setting</td>
      <td>Source data wind direction value</td>
      <td>Imported wind direction value</td>
    </tr>
    <tr>
      <td class="code first_col" rowspan='7'>0, 360</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <td>160</td>
      <td>160</td>
    </tr>
    <tr>
      <td>360</td>
      <td>360</td>
    </tr>
    <tr>
      <td>500</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>-45</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>-9999</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>No data</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td class="code first_col" rowspan='7'>-360, 360</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <td>160</td>
      <td>160</td>
    </tr>
    <tr>
      <td>360</td>
      <td>360</td>
    </tr>
    <tr>
      <td>500</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>-45</td>
      <td>315</td>
    </tr>
    <tr>
      <td>-9999</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>No data</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td class="code first_col" rowspan='7'>-180, 180</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <td>160</td>
      <td>160</td>
    </tr>
    <tr>
      <td>360</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>500</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>-45</td>
      <td>315</td>
    </tr>
    <tr>
      <td>-9999</td>
      <td>None/null</td>
    </tr>
    <tr>
      <td>No data</td>
      <td>None/null</td>
    </tr>
  </tbody>
</table>

The default is `0, 360`.

### `[[FieldMap]]`{#csv_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the CSV source data fields
to WeeWX archive fields. This allows `weectl import` to take a source data 
field, perform the appropriate unit conversion and store the resulting value in 
the appropriate WeeWX archive field. The map consists of one sub-stanza per 
WeeWX archive field being populated using the following format:

```
    [[[weewx_archive_field_name]]]
        source_field = csv_field_name
        unit = weewx_unit_name
        is_cumulative = True | False
        is_text = True | False
```

Where

* `weewx_archive_field_name` is a field in the in-use WeeWX archive table 
  schema
* `csv_field_name` is the name of a field in the CSV source data
* `weewx_unit_name` is a WeeWX unit name; e.g., `degree_C`

Each WeeWX archive field stanza supports the following options:

* `source_field`. The name of the CSV field to be mapped to the WeeWX archive 
  field. Mandatory.
* `unit`. The WeeWX unit name of the units used by `source_field`. Mandatory 
  for non-text source fields. Ignored for source text fields.
* `is_cumulative`. Whether the WeeWX archive field is to be derived from a 
  cumulative source field (e.g., daily rainfall) or not. Optional boolean 
  value. Default is `False`.
* `is_text`. Whether the source field is to be imported as text or not. 
  Optional boolean. Default is `False`.

A mapping is not required for every WeeWX archive field and neither does 
every CSV field need to be included in a mapping.

!!! Note
    Importing of text data into text fields in the WeeWX archive is only 
    supported for WeeWX archive fields that have been configured as text 
    fields. Refer to the Wiki page 
    [Storing text in the database](https://github.com/weewx/weewx/wiki/Storing-text-in-the-database) for details.

If the source data includes a field that contains a WeeWX unit system code 
(i.e. the equivalent of the WeeWX `usUnits` field such as may be obtained from 
WeeWX or wview data) then this field may be mapped to the WeeWX `usUnits` 
field and used to set the units used for all fields being imported. In such 
cases, except for the `[[[dateTime]]]` field map entry, the `weewx_unit_name` 
portion of the imported fields in the field map is not used and may be omitted.

For example, source CSV data with the following structure:

```
date_and_time,temp,humid,wind,dir,dayrain,rad,river,decsription
23 May 2018 13:00,17.4,56,3.0,45,10.0,956,340,'cloudy'
23 May 2018 13:05,17.6,56,1.0,22.5,10.4,746,341,
```

where `temp` is temperature in Celsius, `humid` is humidity in percent, `wind` 
is wind speed in km/h, `dir` is wind direction in degrees, `rainfall` is rain 
in mm, `rad` is radiation in watts per square meter, `river` is river height in 
mm and `description` is a text field might use a field map as follows:

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = date_and_time
        unit = unix_epoch
    [[[outTemp]]]
        source_field = temp
        unit = degree_C
    [[[outHumidity]]]
        source_field = humid
        unit = percent
    [[[windSpeed]]]
        source = wind
        unit = km_per_hour
    [[[windDir]]]
        source_field = dir
        unit = degree_compass
    [[[rain]]]
        source_field = dayrain
        unit = mm
        is_cumulative = True
    [[[radiation]]]
        source_field = rad
        unit = watt_per_meter_squared
    [[[outlook]]]
        source_field = description
        is_text = True
```

If the same source CSV data included a field `unit_info` that contains WeeWX 
unit system data as follows:

```
date_and_time,temp,humid,wind,dir,dayrain,rad,river,decsription,unit_info
23 May 2018 13:00,17.4,56,3.0,45,0.0,956,340,'cloudy',1
23 May 2018 13:05,17.6,56,1.0,22.5,0.4,746,341,'showers developing',16
```

then a field map such as the following might be used:

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = date_and_time
        unit = unix_epoch
    [[[usUnits]]]
        source_field = unit_info
    [[[outTemp]]]
        source_field = temp
    [[[outHumidity]]]
        source_field = humid
    [[[windSpeed]]]
        source = wind
    [[[windDir]]]
        source_field = dir
    [[[rain]]]
        source_field = dayrain
        is_cumulative = True
    [[[radiation]]]
        source_field = rad
    [[[outlook]]]
        source_field = description
        is_text = True
```

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`), and for 
    which there is no field mapping, may be calculated during import by use of 
    the [`calc_missing`](#csv_calc_missing) option in the `[CSV]` section of 
    the import configuration file.

!!! Note
    The `dateTime` field map entry is a special case. Whereas other field map 
    entries may use any supported WeeWX unit name, or no unit name if the 
    `usUnits` field is populated, the `dateTime` field map entry must include 
    the WeeWX unit name `unix_epoch`. This is because `weectl import` uses the 
    [raw_datetime_format](#csv_raw_datetime_format) config option to convert 
    the supplied date-time field data to a Unix epoch timestamp before the 
    field map is applied.


## [WU]

The `[WU]` section contains the options relating to the import of observational 
data from a Weather Underground PWS history.

### `station_id`{#wu_station_id}

The Weather Underground weather station ID of the PWS from which the 
historical data will be imported. 

Mandatory, there is no default.

### `api_key`{#wu_api_key}

The Weather Underground API key to be used to obtain the PWS history data.

Mandatory, there is no default.

!!! Note
    The API key is a seemingly random string of 32 characters used to access 
    the new (2019) Weather Underground API. PWS contributors can obtain an API 
    key by logging onto the Weather Underground internet site and accessing 
    'Member Settings'. 16 character API keys used with the previous Weather 
    Underground API are not supported.

### `interval`{#wu_interval}

Determines how the time interval (WeeWX database field `interval`) between 
successive observations is determined. This option is identical in operation 
to the CSV [interval](#csv_interval) option, but applies to Weather 
Underground imports only. As a Weather Underground PWS history sometimes has 
missing records, the use of `interval = derive` may give incorrect or 
inconsistent interval values. Better results may be obtained by using 
`interval = conf` if the current WeeWX installation has the same 
`archive_interval` as the Weather Underground data, or by using `interval 
= x` where `x` is the time interval in minutes used to upload the Weather 
Underground data. The most appropriate setting will depend on the 
completeness and (time) accuracy of the Weather Underground data being 
imported.

Optional, the default is `derive`.

### `qc`{#wu_qc}

Determines whether simple quality control checks are applied to imported 
data. This option is identical in operation to the CSV [qc](#csv_qc) option 
but applies to Weather Underground imports only. As Weather Underground 
imports at times contain nonsense values, particularly for fields for which 
no data was uploaded to Weather Underground by the PWS, the use of quality 
control checks on imported data can prevent these nonsense values from being 
imported and contaminating the WeeWX database.

Optional, the default is `True`.

### `calc_missing`{#wu_calc_missing}

Determines whether any missing derived observations will be calculated from 
the imported data. This option is identical in operation to the CSV 
[calc_missing](#csv_calc_missing) option but applies to Weather Underground 
imports only.

Optional, the default is `True`.

### `ignore_invalid_data`{#wu_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import 
aborted. This option is identical in operation to the CSV 
[ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Weather 
Underground imports only.

Optional, the default is `True`.

### `tranche`{#wu_tranche}

The number of records written to the WeeWX database in each transaction. 
This option is identical in operation to the CSV [tranche](#csv_tranche) 
option but applies to Weather Underground imports only.

Optional, the default is `250` which should suit most users.

### `wind_direction`{#wu_wind_direction}

Determines the range of acceptable wind direction values in degrees. This 
option is identical in operation to the CSV 
[wind_direction](#csv_wind_direction) option but applies to Weather 
Underground imports only.

Optional, the default is `0, 360`.

### `[[FieldMap]]`{#wu_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the Weather Underground 
source data fields to WeeWX archive fields. This allows `weectl import` to 
take a source data field, perform the appropriate unit conversion and store 
the resulting value in the appropriate WeeWX archive field. Weather 
Underground imports use a simplified map that consists of one sub-stanza per 
WeeWX archive field being populated using the following format:

```
    [[[weewx_archive_field_name]]]
        source_field = wu_field_name
        is_cumulative = True | False
```

Where

* `weewx_archive_field_name` is a field in the in-use WeeWX archive table 
  schema
* `wu_field_name` is the name of a Weather Underground source field as 
  detailed in the _Available Weather Underground import field names_ table 
  below. 

Each WeeWX archive field stanza supports the following option:

* `source_field`. The name of the Weather Underground source field to be  
  mapped to the WeeWX archive field. Mandatory.
* `is_cumulative`. Whether the WeeWX archive field is to be derived from a 
  cumulative source field (e.g., daily rainfall) or not. Optional boolean 
  value. Default is `False`.

A mapping is not required for every WeeWX archive field and neither does 
every Weather Underground field need to be included in a mapping.

<table id="wu-avail-import-field-names-table">
    <caption>Available Weather Underground import field names</caption>
    <tbody>
    <tr class="first_row">
        <td>Field name</td>
        <td>Description</td>
    </tr>
    <tr>
        <td class="first_col code">epoch</td>
        <td>Date and time</td>
    </tr>
    <tr>
        <td class="first_col code">dewptAvg</td>
        <td>Current dewpoint</td>
    </tr>
    <tr>
        <td class="first_col code">heatindexAvg</td>
        <td>Current heat index</td>
    </tr>
    <tr>
        <td class="first_col code">humidityAvg</td>
        <td>Current outside Humidity</td>
    </tr>
    <tr>
        <td class="first_col code">precipRate</td>
        <td>Current rain rate</td>
    </tr>
    <tr>
        <td class="first_col code">precipTotal</td>
        <td>Rainfall since midnight</td>
    </tr>
    <tr>
        <td class="first_col code">pressureAvg</td>
        <td>Current barometric pressure</td>
    </tr>
    <tr>
        <td class="first_col code">solarRadiationHigh</td>
        <td>Current solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">tempAvg</td>
        <td>Outside temperature</td>Current o
    </tr>
    <tr>
        <td class="first_col code">uvHigh</td>
        <td>Current UV index</td>
    </tr>
    <tr>
        <td class="first_col code">windchillAvg</td>
        <td>Current windchill</td>
    </tr>
    <tr>
        <td class="first_col code">winddirAvg</td>
        <td>Current wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">windgustHigh</td>
        <td>Current wind gust</td>
    </tr>
    <tr>
        <td class="first_col code">windspeedAvg</td>
        <td>Current average wind speed</td>
    </tr>
    </tbody>
</table>

!!! Note
    The above field names are internally generated by `weectl import` and do 
    not represent any field names used within Weather Underground. They have 
    only been provided for use in the field map.

For example, the following field map might be used to import outside 
temperature to WeeWX field `outTemp`, outside humidity to WeeWX field 
`outHumidity` and rainfall to WeeWX field `rain`: 

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = epoch
    [[[outTemp]]]
        source_field = tempAvg
    [[[outHumidity]]]
        source_field = humidityAvg
    [[[rain]]]
        source = precipTotal
        is_cumulative = True
```

!!! Note
    The inclusion of `is-cumulative = True` under `[[[rain]]]` as Weather 
    Underground records rainfall as a daily cumulative value.

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for 
    which there is no field mapping may be calculated during import by use 
    of the [`calc_missing`](#wu_calc_missing) option in the `[WU]` section 
    of the import configuration file.

The example Weather Underground import configuration file located in the 
`util/import` directory contains an example field map.


## [Cumulus]

The `[Cumulus]` section contains the options relating to the import of 
observational data from Cumulus monthly log files.

### `directory`{#cumulus_directory}

The full path to the directory containing the Cumulus monthly log files to be 
imported. Do not include a trailing `/`. 

Mandatory, there is no default.

### `source_encoding`{#cumulus_encoding}

The Cumulus monthly log file encoding. This option is identical in operation 
to the CSV [source_encoding](#csv_encoding) option but applies to Cumulus 
imports only.

Optional, the default is `utf-8-sig`.

### `interval`{#cumulus_interval}

Determines how the time interval (WeeWX database field `interval`) between 
successive observations is determined. This option is identical in operation
to the CSV [interval](#csv_interval) option but applies to Cumulus monthly 
log file imports only. As Cumulus monthly log files can, at times, have 
missing entries, the use of `interval = derive` may give incorrect or 
inconsistent interval values. Better results may be obtained by using 
`interval = conf` if the `archive_interval` for the current WeeWX 
installation is the same as the Cumulus 'data log interval' setting used to 
generate the Cumulus monthly log files, or by using `interval = x` where `x` 
is the time interval in minutes used as the Cumulus 'data log interval' 
setting. The most appropriate setting will depend on the completeness and 
(time) accuracy of the Cumulus data being imported.

Optional, the default is `derive`.

### `qc`{#cumulus_qc}

Determines whether simple quality control checks are applied to imported 
data. This option is identical in operation to the CSV [qc](#csv_qc) option 
but applies to Cumulus imports only.

Optional, the default is `True`.

### `calc_missing`{#cumulus_calc_missing}

Determines whether any missing derived observations will be calculated from 
the imported data. This option is identical in operation to the CSV 
[calc_missing](#csv_calc_missing) option but applies to Cumulus imports only.

Optional, the default is `True`.

### `separator`{#cumulus_separator}

The character used as the date field separator in the Cumulus monthly log 
file. A solidus (/) is frequently used, but it may be another character 
depending on the settings on the machine that produced the Cumulus monthly 
log files. This parameter must be included in quotation marks.

Optional, the default is `'/'`.

### `delimiter`{#cumulus_delimiter}

The character used as the field delimiter in the Cumulus monthly log file. 
A comma is frequently used, but it may be another character depending on the 
settings on the machine that produced the Cumulus monthly log files. This 
parameter must be included in quotation marks.

Optional, the default is `','`.

### `decimal`{#cumulus_decimal}

The character used as the decimal point in the Cumulus monthly log files. A 
period is frequently used, but it may be another character depending on the 
settings on the machine that produced the Cumulus monthly log files. This 
parameter must be included in quotation marks.

Optional, the default is `'.'`.

### `ignore_invalid_data`{#cumulus_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import 
aborted. This option is identical in operation to the CSV 
[ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Cumulus 
monthly log file imports only.

Optional, the default is `True`.

### `tranche`{#cumulus_tranche}

The number of records written to the WeeWX database in each transaction. This 
option is identical in operation to the CSV [tranche](#csv_tranche) option 
but applies to Cumulus monthly log file imports only.

Optional, the default is `250` which should suit most users.

### `UV_sensor`{#cumulus_UV}

Enables `weectl import` to distinguish between the case where a UV sensor is 
present and the UV index is 0 and where no UV sensor is present and the UV 
index is 0. This option is identical in operation to the CSV 
[UV_sensor](#csv_UV) option but applies to Cumulus monthly log file imports 
only.

Optional, the default is `True`.

### `solar_sensor`{#cumulus_solar}

Enables `weectl import` to distinguish between the case where a solar 
radiation sensor is present and solar radiation is 0 and where no solar 
radiation sensor is present and solar radiation is 0. This option is 
identical in operation to the CSV [solar_sensor](#csv_solar) option but 
applies to Cumulus monthly log file imports only.

Optional, the default is `True`.

### `[[FieldMap]]`{#cumulus_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the Cumulus source data 
fields to WeeWX archive fields. This allows `weectl import` to take a source 
data field, perform the appropriate unit conversion and store the resulting 
value in the appropriate WeeWX archive field. The map consists of one 
sub-stanza per WeeWX archive field being populated using the following 
format:

```
    [[[weewx_archive_field_name]]]
        source_field = cumulus_field_name
        unit = weewx_unit_name
        is_cumulative = True | False
        is_text = True | False
```

Where

* `weewx_archive_field_name` is a field in the in-use WeeWX archive table 
  schema
* `cumulus_field_name` is the name of a Cumulus source field as detailed in 
  the _Available Cumulus import field names_ table below. 
* `weewx_unit_name` is a WeeWX unit name; e.g., `degree_C`
* `is_text`. Whether the source field is to be imported as text or not. 
  Optional boolean. Default is `False`.

Each WeeWX archive field stanza supports the following options:

* `source_field`. The name of the Cumulus field to be mapped to the WeeWX 
  archive field. Mandatory.
* `unit`. The WeeWX unit name of the units used by `source_field`. Mandatory.
* `is_cumulative`. Whether the WeeWX archive field is to be derived from a 
  cumulative source field (e.g., daily rainfall) or not. Optional boolean 
  value. Default is `False`.

A mapping is not required for every WeeWX archive field and neither does 
every Cumulus field need to be included in a mapping.

!!! Note
    The `unit` option setting for each field map entry will depend on the 
    Cumulus settings used to generate the Cumulus monthly log files. 
    Depending on the Cumulus field type, the supported WeeWX units names 
    for that field may only be a subset of the corresponding WeeWX unit 
    names; e.g., WeeWX supports temperatures in Celsius, Fahrenheit and 
    Kelvin, but Cumulus logs may only include temperatures in Celsius or 
    Fahrenheit. Refer to [_Units_](../reference/units.md) for details of 
    available WeeWX unit names. 

<table id="cumulus-avail-import-field-names-table">
    <caption>Available Cumulus import field names</caption>
    <tbody>
    <tr class="first_row">
        <td>Field name</td>
        <td>Description</td>
    </tr>
    <tr>
        <td class="first_col code">datetime</td>
        <td>Date and time</td>
    </tr>
    <tr>
        <td class="first_col code">annual_et</td>
        <td>Annual evapotranspiration</td>
    </tr>
    <tr>
        <td class="first_col code">avg_wind_speed</td>
        <td>Average wind speed</td>
    </tr>
    <tr>
        <td class="first_col code">cur_app_temp</td>
        <td>Current apparent temperature</td>
    </tr>
    <tr>
        <td class="first_col code">avg_wind_bearing</td>
        <td>Current wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">cur_dewpoint</td>
        <td>Current dew point</td>
    </tr>
    <tr>
        <td class="first_col code">cur_et</td>
        <td>Evapotranspiration</td>
    </tr>
    <tr>
        <td class="first_col code">cur_heatindex</td>
        <td>Current heat index</td>
    </tr>
    <tr>
        <td class="first_col code">cur_in_hum</td>
        <td>Current inside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">cur_in_temp</td>
        <td>Current inside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">cur_out_hum</td>
        <td>Current outside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">cur_out_temp</td>
        <td>Current outside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">cur_rain_rate</td>
        <td>Current rain rate</td>
    </tr>
    <tr>
        <td class="first_col code">cur_slp</td>
        <td>Current barometric pressure</td>
    </tr>
    <tr>
        <td class="first_col code">cur_solar</td>
        <td>Current solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">cur_tmax_solar</td>
        <td>Current theoretical maximum solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">cur_uv</td>
        <td>Current UV index</td>
    </tr>
    <tr>
        <td class="first_col code">cur_wind_bearing</td>
        <td>Current wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">cur_windchill</td>
        <td>Current windchill</td>
    </tr>
    <tr>
        <td class="first_col code">day_rain</td>
        <td>Total rainfall since the daily rollover</td>
    </tr>
    <tr>
        <td class="first_col code">day_rain_rg11</td>
        <td>Today's RG-11 rainfall</td>
    </tr>
    <tr>
        <td class="first_col code">day_sunshine_hours</td>
        <td>Today's sunshine hours</td>
    </tr>
    <tr>
        <td class="first_col code">gust_wind_speed</td>
        <td>Wind gust speed</td>
    </tr>
    <tr>
        <td class="first_col code">latest_wind_gust</td>
        <td>Latest measured wind speed</td>
    </tr>
    <tr>
        <td class="first_col code">midnight_rain</td>
        <td>Total rainfall since midnight</td>
    </tr>
    <tr>
        <td class="first_col code">rain_counter</td>
        <td>Total rainfall counter</td>
    </tr>
    </tbody>
</table>

!!! Note
    The above field names are internally generated by `weectl import` and do 
    not represent any field names used within Cumulus. They have only been 
    provided for use in the field map.

For example, the following field map might be used to import outside 
temperature to WeeWX field `outTemp`, outside humidity to WeeWX field 
`outHumidity` and extra temperature 1 to WeeWX field `poolTemp`: 

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = datetime
        unit = unix_epoch
    [[[outTemp]]]
        source_field = temp
        unit = degree_C
    [[[outHumidity]]]
        source_field = humid
        unit = percent
    [[[poolTemp]]]
        source = temp1
        unit = degree_C
```

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for 
    which there is no field mapping may be calculated during import by use of 
    the [`calc_missing`](#cumulus_calc_missing) option in the `[Cumulus]` 
    section of the import configuration file.

!!! Note
    The `dateTime` field map entry is a special case. Whereas other field map 
    entries may use any WeeWX unit name for a unit supported by the import 
    source, the `dateTime` field map entry must use the WeeWX unit name 
    `unix_epoch`.

The example Cumulus import configuration file located in the `util/import` 
directory contains an example field map.


## [WD]

The `[WD]` section contains the options relating to the import of 
observational data from Weather Display monthly log files.

### `directory`{#wd_directory}

The full path to the directory containing the Weather Display monthly log 
files to be imported. Do not include a trailing `/`.

Mandatory, there is no default.

### `logs_to_process`{#wd_logs_to_process}

The Weather Display monthly log files to be processed. Weather Display uses 
multiple files to record each month of data. Which monthly log files are 
produced depends on the Weather Display configuration and the capabilities of 
the weather station. `weectl import` supports the following Weather Display
monthly log files:

* `MMYYYYlg.txt`
* `MMYYYYlgcsv.csv` (csv format version of `MMYYYYlg.txt`)
* `MMYYYYvantagelog.txt`
* `MMYYYYvantagelogcsv.csv` (csv format version of `MMYYYYvantagelog.txt`)
* `MMYYYYvantageextrasensorslog.csv`

where MM is a one or two-digit month and YYYY is a four digit year

The format for the `logs_to_process` setting is:

```
logs_to_process = [lg.txt, | logcsv.csv, | vantagelog.txt, | vantagelogcsv.
csv, | vantageextrasensorslog.csv]
```

!!! Note
    The leading MMYYYY is omitted when listing the monthly log files to be 
    processed using the `logs_to_process` setting. Inclusion of the leading 
    MMYYYY will cause the import to fail.

!!! Note
    The `MMYYYYlgcsv.csv` and `MMYYYYvantagelogcsv.csv` log files are CSV 
    versions of `MMYYYYlg.txt` and `MMYYYYvantagelog.txt` respectively. 
    Either the `.txt` or `.csv` version of these files should be used but 
    not both.

The monthly log files selected for processing should be chosen carefully as 
the selected log files will determine the Weather Display data fields 
available for import. `weectl import` is able to import the following data 
from the indicated monthly log files:

* `MMYYYYlg.txt`/`MMYYlgcsv.csv`:
    * `average wind speed`
    * `barometer`
    * `date and time`
    * `dew point`
    * `heat index`
    * `outside humidity`
    * `outside temperature`
    * `rain fall`
    * `wind direction`
    * `wind gust speed`

* `MMYYYYvantagelog.txt`/`MMYYYYvantagelogcsv.csv`:
    * `date and time`
    * `soil moisture`
    * `soil temperature`
    * `solar radiation`
    * `UV index`

* `MMYYYYvantageextrasensorslog.csv`:
    * `date and time`
    * `extra humidity 1`
    * `extra humidity 2`
    * `extra humidity 3`
    * `extra humidity 4`
    * `extra humidity 5`
    * `extra humidity 6`
    * `extra temperature 1`
    * `extra temperature 2`
    * `extra temperature 3`
    * `extra temperature 4`
    * `extra temperature 5`
    * `extra temperature 6`

!!! Note
    Whilst the above log files may contain the indicated data the data may 
    only be imported subject to a suitable field map and in-use WeeWX archive 
    table schema (refer to the [[[FieldMap]]](#wd_fieldmap) option).

Optional, the default is `lg.txt, vantagelog.txt, vantageextrasensorslog.csv`.

### `source_encoding`{#wd_encoding}

The Weather Display monthly log file encoding. This option is identical in 
operation to the CSV [source_encoding](#csv_encoding) option but applies to 
Weather Display imports only.

Optional, the default is `utf-8-sig`.

### `interval`{#wd_interval}

Determines how the time interval (WeeWX database field `interval`) between 
successive observations is determined. This option is identical in operation 
to the CSV [interval](#csv_interval) option but applies to Weather Display 
monthly log file imports only. As Weather Display log files nominally have 
entries at one minute intervals the recommended approach is to set 
`interval = 1`. As Weather Display monthly log files can, at times, have 
missing entries, the use of `interval = derive` may give incorrect or 
inconsistent interval values. If then `archive_interval` for the current 
WeeWX installation is 1 minute `interval = conf` may be used. In most cases 
the most appropriate setting will be `interval = 1`.

Optional, the default is `1`.

### `qc`{#wd_qc}

Determines whether simple quality control checks are applied to imported 
data. This option is identical in operation to the CSV [qc](#csv_qc) option 
but applies to Weather Display imports only.

Optional, the default is `True`.

### `calc_missing`{#wd_calc_missing}

Determines whether any missing derived observations will be calculated from 
the imported data. This option is identical in operation to the CSV 
[calc_missing](#csv_calc_missing) option but applies to Weather Display 
imports only.

Optional, the default is `True`.

### `txt_delimiter`{#wd_txt_delimiter}

The character used as the field delimiter in Weather Display text format 
monthly log files (.txt files). A space is normally used but another 
character may be used if necessary. This parameter must be included in 
quotation marks.

Optional, the default is `' '`.

### `csv_delimiter`{#wd_csv_delimiter}

The character used as the field delimiter in Weather Display csv format 
monthly log files (.csv files). A comma is normally used but another 
character may be used if necessary. This parameter must be included in 
quotation marks.

Optional, the default is `','`.

### `decimal`{#wd_decimal}

The character used as the decimal point in the Weather Display monthly log 
files. A period is frequently used but another character may be used if 
necessary. This parameter must be included in quotation marks.

Optional, the default is `'.'`.

### `ignore_missing_log`{#wd_ignore_missing_log}

Determines whether missing log files are to be ignored or the import aborted. 
Weather Display log files are complete in themselves and a missing log file 
will have no effect other than there will be no imported data for the period 
covered by the missing log file.

Optional, the default is `True`.

### `ignore_invalid_data`{#wd_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import 
aborted. This option is identical in operation to the CSV 
[ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Weather 
Display monthly log file imports only.

Optional, the default is `True`.

### `tranche`{#wd_tranche}

The number of records written to the WeeWX database in each transaction. 
This option is identical in operation to the CSV [tranche](#csv_tranche) 
option but applies to Weather Display monthly log file imports only.

Optional, the default is `250` which should suit most users.

### `UV_sensor`{#wd_UV}

Enables `weectl import` to distinguish between the case where a UV sensor is 
present and the UV index is 0 and where no UV sensor is present and the UV 
index is 0. This option is identical in operation to the CSV 
[UV_sensor](#csv_UV) option but applies to Weather Display monthly log file 
imports only.

Optional, the default is `True`.

### `solar_sensor`{#wd_solar}

Enables `weectl import` to distinguish between the case where a solar 
radiation sensor is present and solar radiation is 0 and where no solar 
radiation sensor is present and solar radiation is 0. This option is identical 
in operation to the CSV [solar_sensor](#csv_solar) option but applies to 
Weather Display monthly log file imports only.

Optional, the default is `True`.

### `ignore_extreme_temp_hum`{#wd_ignore_extreme_temp_hum}

Determines whether extreme temperature and humidity values are ignored. 
Weather Display log files record the value 255 for temperature and humidity 
fields if no corresponding sensor is present. Setting 
`ignore_extreme_temp_hum = True` will cause temperature and humidity 
values of 255 to be ignored. Setting `ignore_extreme_temp_hum = False` will 
cause temperature and humidity values of 255 to be treated as valid data to 
be imported.

Optional, the default is `True`.

!!! Note
    Setting `ignore_extreme_temp_hum = False` will cause temperature and 
    humidity values of 255 to be imported; however, these values may be 
    rejected by the simple quality control checks implemented if `qc = True` 
    is used.

### `[[FieldMap]]`{#wd_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the Weather Display 
source data fields to WeeWX archive fields. This allows `weectl import` to 
take a source data field, perform the appropriate unit conversion and store 
the resulting value in the appropriate WeeWX archive field. The map consists 
of one sub-stanza per WeeWX archive field being populated using the following 
format:

```
    [[[weewx_archive_field_name]]]
        source_field = wd_field_name
        unit = weewx_unit_name
        is_cumulative = True | False
        is_text = True | False
```

Where

* `weewx_archive_field_name` is a field in the in-use WeeWX archive table 
  schema
* `wd_field_name` is the name of a Weather Display source field as detailed 
  in the _Available Weather Display import field names_ table below. 
* `weewx_unit_name` is a WeeWX unit name; e.g., `degree_C`

Each WeeWX archive field stanza supports the following options:

* `source_field`. The name of the Weather Display field to be mapped to the 
  WeeWX archive field. Mandatory.
* `unit`. The WeeWX unit name of the units used by `source_field`. Mandatory.
* `is_cumulative`. Whether the WeeWX archive field is to be derived from a 
  cumulative source field (e.g., daily rainfall) or not. Optional boolean 
  value. Default is `False`.
* `is_text`. Whether the source field is to be imported as text or not. 
  Optional boolean. Default is `False`.

A mapping is not required for every WeeWX archive field and neither does 
every Weather Display field need to be included in a mapping.

!!! Note
    The `unit` option setting for each field map entry will depend on the 
    Weather Display settings used to generate the Weather Display log files. 
    Depending on the Weather Display field type, the supported WeeWX units 
    names for that field may only be a subset of the corresponding WeeWX unit 
    names; e.g., WeeWX supports temperatures in Celsius, Fahrenheit and 
    Kelvin, but Weather Display log files may only include temperatures in 
    Celsius or Fahrenheit. Refer to [_Units_](../reference/units.md) for 
    details of available WeeWX unit names. 

<table id="wd-avail-import-field-names-table">
    <caption>Available Weather Display import field names</caption>
    <tbody>
    <tr class="first_row">
        <td>Field name</td>
        <td>Description</td>
    </tr>
    <tr>
        <td class="first_col code">datetime</td>
        <td>Date and time</td>
    </tr>
    <tr>
        <td class="first_col code">barometer</td>
        <td>Barometric pressure</td>
    </tr>
    <tr>
        <td class="first_col code">dailyet</td>
        <td>Daily evapotranspiration</td>
    </tr>
    <tr>
        <td class="first_col code">dewpoint</td>
        <td>Dew point</td>
    </tr>
    <tr>
        <td class="first_col code">direction</td>
        <td>Wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">gustspeed</td>
        <td>Wind gust speed</td>
    </tr>
    <tr>
        <td class="first_col code">heatindex</td>
        <td>Heat index</td>
    </tr>
    <tr>
        <td class="first_col code">humidity</td>
        <td>Outside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">hum1</td>
        <td>Extra humidity 1</td>
    </tr>
    <tr>
        <td class="first_col code">hum2</td>
        <td>Extra humidity 2</td>
    </tr>
    <tr>
        <td class="first_col code">hum3</td>
        <td>Extra humidity 3</td>
    </tr>
    <tr>
        <td class="first_col code">hum4</td>
        <td>Extra humidity 4</td>
    </tr>
    <tr>
        <td class="first_col code">hum5</td>
        <td>Extra humidity 5</td>
    </tr>
    <tr>
        <td class="first_col code">hum6</td>
        <td>Extra humidity 6</td>
    </tr>
    <tr>
        <td class="first_col code">hum7</td>
        <td>Extra humidity 7</td>
    </tr>
    <tr>
        <td class="first_col code">radiation</td>
        <td>Solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">rainlastmin</td>
        <td>Rainfall in the last 1 minute</td>
    </tr>
    <tr>
        <td class="first_col code">soilmoist</td>
        <td>Soil moisture</td>
    </tr>
    <tr>
        <td class="first_col code">soiltemp</td>
        <td>Soil temperature</td>
    </tr>
    <tr>
        <td class="first_col code">temperature</td>
        <td>Outside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">temp1</td>
        <td>Extra temperature 1</td>
    </tr>
    <tr>
        <td class="first_col code">temp2</td>
        <td>Extra temperature 2</td>
    </tr>
    <tr>
        <td class="first_col code">temp3</td>
        <td>Extra temperature 3</td>
    </tr>
    <tr>
        <td class="first_col code">temp4</td>
        <td>Extra temperature 4</td>
    </tr>
    <tr>
        <td class="first_col code">temp5</td>
        <td>Extra temperature 5</td>
    </tr>
    <tr>
        <td class="first_col code">temp6</td>
        <td>Extra temperature 6</td>
    </tr>
    <tr>
        <td class="first_col code">temp7</td>
        <td>Extra temperature 7</td>
    </tr>
    <tr>
        <td class="first_col code">uv</td>
        <td>UV index</td>
    </tr>
    <tr>
        <td class="first_col code">windspeed</td>
        <td>Average wind speed</td>
    </tr>
    </tbody>
</table>

!!! Note
    The above field names are internally generated by `weectl import` and do 
    not represent any field names used within Weather Display. They have only
    been provided for use in the field map.

For example, the following field map might be used to import outside 
temperature to WeeWX field `outTemp`, outside humidity to WeeWX field 
`outHumidity` and extra temperature 1 to WeeWX field `poolTemp`: 

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = datetime
        unit = unix_epoch
    [[[outTemp]]]
        source_field = temperature
        unit = degree_C
    [[[outHumidity]]]
        source_field = humidity
        unit = percent
    [[[poolTemp]]]
        source = temp1
        unit = degree_C
```

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for 
    which there is no field mapping may be calculated during import by use of 
    the [`calc_missing`](#wd_calc_missing) option in the `[WD]` section of 
    the import configuration file.

!!! Note
    The `dateTime` field map entry is a special case. Whereas other field 
    map entries may use any WeeWX unit name for a unit supported by the 
    import source, the `dateTime` field map entry must use the WeeWX unit 
    name `unix_epoch`.

The example Weather Display import configuration file located in the 
`util/import` directory contains an example field map.


## [WeatherCat]

The `[WeatherCat]` section contains the options relating to the import of 
observational data from WeatherCat monthly .cat files.

### `directory`{#wcat_directory}

The full path to the directory containing the year directories that contain 
the WeatherCat monthly .cat files to be imported. Do not include a trailing 
`/`.

Mandatory, there is no default.

### `source_encoding`{#wcat_encoding}

The WeatherCat monthly .cat file encoding. This option is identical in 
operation to the CSV [source_encoding](#csv_encoding) option but applies to 
WeatherCat imports only.

Optional, the default is `utf-8-sig`.

### `interval`{#wcat_interval}

Determines how the time interval (WeeWX database field `interval`) between 
successive observations is determined. This option is identical in operation 
to the CSV [interval](#csv_interval) option but applies to WeatherCat imports 
only. As WeatherCat monthly .cat files can, at times, have missing entries,
the use of `interval = derive` may give incorrect or inconsistent interval 
values. Better results may be obtained by using `interval = conf` if the 
`archive_interval` for the current WeeWX installation is the same as the 
WeatherCat .cat file log interval, or by using `interval = x` where `x` is 
the time interval in minutes used in the WeatherCat monthly .cat file(s). The 
most appropriate setting will depend on the completeness and (time) accuracy 
of the WeatherCat data being imported.

Optional, the default is `derive`.

### `qc`{#wcat_qc}

Determines whether simple quality control checks are applied to imported 
data. This option is identical in operation to the CSV [qc](#csv_qc) option 
but applies to WeatherCat imports only.

Optional, the default is `True`.

### `calc_missing`{#wcat_calc_missing}

Determines whether any missing derived observations will be calculated from 
the imported data. This option is identical in operation to the CSV 
[calc_missing](#csv_calc_missing) option but applies to WeatherCat imports only.

Optional, the default is `True`.

### `decimal`{#wcat_decimal}

The character used as the decimal point in the WeatherCat monthly .cat files. 
This parameter must be included in quotation marks.

Optional, the default is `'.'`.

### `tranche`{#wcat_tranche}

The number of records written to the WeeWX database in each transaction. This 
option is identical in operation to the CSV [tranche](#csv_tranche) option 
but applies to WeatherCat imports only.

Optional, the default is `250` which should suit most users.

### `UV_sensor`{#wcat_UV}

Enables `weectl import` to distinguish between the case where a UV sensor is 
present and the UV index is 0 and where no UV sensor is present and the UV 
index is 0. This option is identical in operation to the CSV 
[UV_sensor](#csv_UV) option but applies to WeatherCat imports only.

Optional, the default is `True`.

### `solar_sensor`{#wcat_solar}

Enables `weectl import` to distinguish between the case where a solar 
radiation sensor is present and solar radiation is 0 and where no solar 
radiation sensor is present and solar radiation is 0. This option is 
identical in operation to the CSV [solar_sensor](#csv_solar) option but 
applies to WeatherCat imports only.

Optional, the default is `True`.

### `[[FieldMap]]`{#wcat_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the WeatherCat source data 
fields to WeeWX archive fields. This allows `weectl import` to take a source 
data field, perform the appropriate unit conversion and store the resulting 
value in the appropriate WeeWX archive field. The map consists of one 
sub-stanza per WeeWX archive field being populated using the following format:

```
    [[[weewx_archive_field_name]]]
        source_field = wc_field_name
        unit = weewx_unit_name
        is_cumulative = True | False
        is_text = True | False
```

Where

* `weewx_archive_field_name` is a field in the in-use WeeWX archive table 
  schema
* `wc_field_name` is the nameof a WeatherCat source field as detailed in the 
  _Available WeatherCat import field names_ table below. 
* `weewx_unit_name` is a WeeWX unit name; e.g., `degree_C`

Each WeeWX archive field stanza supports the following options:

* `source_field`. The name of the WeatherCat field to be mapped to the WeeWX 
  archive field. Mandatory.
* `unit`. The WeeWX unit name of the units used by `source_field`. Mandatory.
* `is_cumulative`. Whether the WeeWX archive field is to be derived from a 
  cumulative source field (e.g., daily rainfall) or not. Optional boolean 
  value. Default is `False`.
* `is_text`. Whether the source field is to be imported as text or not. 
  Optional boolean. Default is `False`.

!!! Note
    The `unit` option setting for each field map entry will depend on the 
    WeatherCat settings used to generate the WeatherCat .cat files. 
    Depending on the WeatherCat field type, the supported WeeWX unit names  
    for that field may only be a subset of the corresponding WeeWX unit names;
    e.g., WeeWX supports temperatures in Celsius, Fahrenheit and Kelvin, but 
    WeatherCat .cat files may only include temperatures in Celsius or 
    Fahrenheit. Refer to [_Units_](../reference/units.md) for details of 
    available WeeWX unit names.

A mapping is not required for every WeeWX archive field and neither does 
every WeatherCat field need to be included in a mapping.

<table id="wc-avail-import-field-names-table">
    <caption>Available WeatherCat import field names</caption>
    <tbody>
    <tr class="first_row">
        <td>Field name</td>
        <td>Description</td>
    </tr>
    <tr>
        <td class="first_col code">datetime</td>
        <td>date and time</td>
    </tr>
    <tr>
        <td class="first_col code">Pr</td>
        <td>Barometric pressure</td>
    </tr>
    <tr>
        <td class="first_col code">D</td>
        <td>Dew point</td>
    </tr>
    <tr>
        <td class="first_col code">Hi</td>
        <td>Inside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">Ti</td>
        <td>Inside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">H1</td>
        <td>Extra humidity 1</td>
    </tr>
    <tr>
        <td class="first_col code">H2</td>
        <td>Extra humidity 2</td>
    </tr>
    <tr>
        <td class="first_col code">T1</td>
        <td>Extra temperature 1</td>
    </tr>
    <tr>
        <td class="first_col code">T2</td>
        <td>Extra temperature 2</td>
    </tr>
    <tr>
        <td class="first_col code">T3</td>
        <td>Extra temperature 3</td>
    </tr>
    <tr>
        <td class="first_col code">Lt1</td>
        <td>Leaf temperature 1</td>
    </tr>
    <tr>
        <td class="first_col code">Lt2</td>
        <td>Leaf temperature 2</td>
    </tr>
    <tr>
        <td class="first_col code">Lw1</td>
        <td>Leaf wetness 1</td>
    </tr>
    <tr>
        <td class="first_col code">Lw2</td>
        <td>Leaf wetness 2</td>
    </tr>
    <tr>
        <td class="first_col code">H</td>
        <td>Outside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">T</td>
        <td>Outside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">P</td>
        <td>Precipitation</td>
    </tr>
    <tr>
        <td class="first_col code">Sm1</td>
        <td>Soil moisture 1</td>
    </tr>
    <tr>
        <td class="first_col code">Sm2</td>
        <td>Soil moisture 2</td>
    </tr>
    <tr>
        <td class="first_col code">Sm3</td>
        <td>Soil moisture 3</td>
    </tr>
    <tr>
        <td class="first_col code">Sm4</td>
        <td>Soil moisture 4</td>
    </tr>
    <tr>
        <td class="first_col code">St1</td>
        <td>Soil temperature 1</td>
    </tr>
    <tr>
        <td class="first_col code">St2</td>
        <td>Soil temperature 2</td>
    </tr>
    <tr>
        <td class="first_col code">St3</td>
        <td>Soil temperature 3</td>
    </tr>
    <tr>
        <td class="first_col code">St4</td>
        <td>Soil temperature 4</td>
    </tr>
    <tr>
        <td class="first_col code">S</td>
        <td>Solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">U</td>
        <td>UV index</td>
    </tr>
    <tr>
        <td class="first_col code">Wc</td>
        <td>Windchill</td>
    </tr>
    <tr>
        <td class="first_col code">Wd</td>
        <td>Wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">Wg</td>
        <td>Wind gust speed</td>
    </tr>
    <tr>
        <td class="first_col code">W</td>
        <td>Wind speed</td>
    </tr>
    </tbody>
</table>

!!! Note
    The above field names are internally generated by `weectl import` and do 
    not represent any field names used within WeatherCat. They have only been
    provided for use in the field map.

For example, the following field map might be used to import outside 
temperature to WeeWX field `outTemp`, outside humidity to WeeWX field 
`outHumidity` and extra temperature 1 to WeeWX field `poolTemp`: 

```
[[FieldMap]]
    [[[dateTime]]]
        source_field = datetime
        unit = unix_epoch
    [[[outTemp]]]
        source_field = T
        unit = degree_C
    [[[outHumidity]]]
        source_field = H
        unit = percent
    [[[poolTemp]]]
        source = T1
        unit = degree_C
```

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for 
    which there is no field mapping may be calculated during import by use of 
    the [`calc_missing`](#wc_calc_missing) option in the `[WeatherCat]` 
    section of the import configuration file.

!!! Note
    The `dateTime` field map entry is a special case. Whereas other field map 
    entries may use any WeeWX unit name for a unit supported by the import 
    source, the `dateTime` field map entry must use the WeeWX unit name 
    `unix_epoch`.

The example WeatherCat import configuration file located in the `util/import`
directory contains an example field map.