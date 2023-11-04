## The import configuration file

`wee_import` requires a second configuration file, the import configuration
file, in addition to the standard WeeWX configuration file. The import
configuration file specifies the import type and various options associated
with each type of import. The import configuration file is specified using the
mandatory `--import-config` option. How you construct the import configuration
file is up to you; however, the recommended method is to copy one of the
example import configuration files located in the `/home/weewx/util/import` or
`/etc/weewx/import` directory as applicable, modify the configuration options
in the newly copied file to suit the import to be performed and then use this
file as the import configuration file.

Following is the definitive guide to the options available in the import
configuration file. Default values are provided for a number of options,
meaning that if they are not listed in the import configuration file at all
`wee_import` will pick sensible values. When the documentation below gives a
default value this is the value that will be used if the option is omitted.

#### `source`{#import_config_source}

The `source` option determines the type of import to be performed by
`wee_import`. The option is mandatory and must be set to one of the following:

* `CSV` to import from a single CSV format file.
* `WU` to import from a Weather Underground PWS history
* `Cumulus` to import from one or more Cumulus monthly log files.
* `WD` to import from one or more Weather Display monthly log files.
* `WeatherCat` to import from one or more WeatherCat monthly .cat files.

There is no default.

### [CSV]

The `[CSV]` section contains the options controlling the import of
observational data from a CSV format file.

#### `file`{#csv_file}

The file containing the CSV format data to be used as the source during the
import. Include full path and filename. There is no default.

#### `source_encoding`{#csv_encoding}

The source file encoding. This parameter is optional and should only need be
used if the source file uses an encoding other than UTF-8 or an ASCII
compatible encoding. If used, the setting used should be a <a href="https://docs.python.org/3/library/codecs.html#standard-encodings">Python Standard Encoding</a>.

The default value is `utf-8-sig`.

#### `delimiter`{#csv_delimiter}

The character used to separate fields. Default is `,` (comma).

#### `decimal`{#csv_decimal}

The character used as the decimal point in the source files. A full stop is
frequently used, but it may be another character. This parameter must be
included in quotation marks. Default is `'.'`.

#### `interval`{#csv_interval}

Determines how the time interval (WeeWX archive table field `interval`)
between successive observations is derived. The interval can be derived by one
of three methods:

* The interval can be calculated as the time, rounded to the nearest minute, between the date-time of successive records. This method is suitable when the data was recorded at fixed intervals and there are NO missing records in the source data. Use of this method when there are missing records in the source data can compromise the integrity of the WeeWX statistical data. Select this method by setting `interval = derive`.

* The interval can be set to the same value as the `archive_interval` setting under `[StdArchive]` in `weewx.conf`. This setting is useful if the data was recorded at fixed intervals but there are some missing records and the fixed interval is the same as the `archive_interval` setting under `[StdArchive]` in `weewx.conf`. Select this method by setting `interval = conf`.

* The interval can be set to a fixed number of minutes. This setting is useful if the source data was recorded at fixed intervals but there are some missing records and the fixed interval is different to the `archive_interval` setting under `[StdArchive]` in `weewx.conf`. Select this method by setting `interval = x` where `x` is an integer number of minutes.

The default value is `derive`. If the CSV source data records are equally spaced in time, but some records are missing, then a better result may be achieved using `conf` or a fixed interval setting.

#### `qc`{#csv_qc}

Determines whether simple quality control checks are applied to imported data. Setting `qc = True` will result in `wee_import` applying the WeeWX `StdQC` minimum and maximum checks to any imported observations. `wee_import` quality control checks use the same configuration settings, and operate in the same manner, as the [_StdQC_](../../reference/weewx-options/stdqc) service. For example, for minimum/maximum quality checks, if an observation falls outside of the quality control range for that observation, the observation will be set to `None`. In such cases you will be alerted through a short message similar to:

```
2016-01-12 10:00:00 AEST (1452556800) record value 'outTemp' 194.34 outside limits (0.0, 120.0)
```

As derived observations are calculated after the quality control check is applied, derived observations are not subject to quality control checks. Setting `qc = False` will result in `wee_import` not applying quality control checks to imported data.

The default is `True`.

#### `calc_missing`{#csv_calc_missing}

Determines whether any missing derived observations will be calculated from the imported data. Setting `calc_missing = True` will result in `wee_import` using the WeeWX `StdWXCalculate` service to calculate any missing derived observations from the imported data. Setting `calc_missing = False` will result in WeeWX leaving any missing derived observations as `None`. See [_[StdWXCalculate]_](../../reference/weewx-options/stdwxcalculate) for details of the observations the `StdWXCalculate` service can calculate.

The default is `True`.

#### `ignore_invalid_data`{#csv_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import aborted. If invalid data is found in a source field and `ignore_invalid_data` is `True` the corresponding WeeWX destination field is set to `None` and the import continues. If invalid data is found in a source field and `ignore_invalid_data` is `False` the import is aborted.

The default is `True`.

#### `tranche`{#csv_tranche}

To speed up database operations imported records are committed to database in groups of records rather than individually. The size of the group is set by the `tranche` parameter. Increasing the `tranche` parameter may result in a slight speed increase but at the expense of increased memory usage. Decreasing the `tranche` parameter will result in less memory usage but at the expense of more frequent database access and likely increased time to import.

The default is `250` which should suit most users.

#### `UV_sensor`{#csv_UV}

WeeWX records a `None/null` for UV when no UV sensor is installed, whereas some weather station software records a value of 0 for UV index when there is no UV sensor installed. The `UV_sensor` parameter enables `wee_import` to distinguish between the case where a UV sensor is present and the UV index is 0 and the case where no UV sensor is present and UV index is 0. `UV_sensor = False` should be used when no UV sensor was used in producing the source data. `UV_sensor = False` will result in `None/null` being recorded in the WeeWX archive field `UV` irrespective of any UV observations in the source data. `UV_sensor = True` should be used when a UV sensor was used in producing the source data. `UV_sensor = True` will result in UV observations in the source data being stored in the WeeWX archive field `UV`.

The default is `True`.

#### `solar_sensor`{#csv_solar}

WeeWX records a `None/null` when no solar radiation sensor is installed, whereas some weather station software records a value of 0 for solar radiation when there is no solar radiation sensor installed. The `solar_sensor` parameter enables `wee_import` to distinguish between the case where a solar radiation sensor is present and solar radiation is 0 and the case where no solar radiation sensor is present and solar radiation is 0. `solar_sensor = False` should be used when no solar radiation sensor was used in producing the source data. `solar_sensor = False` will result in `None/null` being recorded in the WeeWX archive field `radiation` irrespective of any solar radiation observations in the source data. `solar_sensor = True` should be used when a solar radiation sensor was used in producing the source data. `solar_sensor = True` will result in solar radiation observations in the source data being stored in the WeeWX archive field `radiation`.

The default is `True`.

#### `raw_datetime_format`{#csv_raw_datetime_format}

WeeWX records each record with a unique unix epoch timestamp, whereas many weather station applications or web sources export observational data with a human-readable date-time. This human-readable date-time is interpreted according to the format set by the `raw_datetime_format` option. This option consists of [Python strptime() format codes](https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior) and literal characters to represent the date-time data being imported.

For example, if the source data uses the format 23 January 2015 15:34 the appropriate setting for `raw_datetime_format` would be `%d %B %Y %H:%M`, 9:25:00 12/28/16 would use `%H:%M:%S %m/%d/%y`. If the source data provides a unix epoch timestamp as the date-time field the unix epoch timestamp is used directly and the `raw_datetime_format` option is ignored.

The default is `%Y-%m-%d %H:%M:%S`.

!!! Note
    `wee_import` does not support the construction of the unique record date
    time stamp from separate date and time fields, rather the date-time
    information for each imported record must be contained in a single
    field. CSV data containing separate date and time fields may require
    further manual processing before they can be imported.

#### `rain`{#csv_rain}

The WeeWX `rain` field records rainfall that was recorded in the preceding archive period, so for a five-minute archive period the `rain` field in each archive record would contain the total rainfall that fell in the previous five minutes. Many weather station applications provide a daily or yearly total. `wee_import` can derive the WeeWX `rain` field in one of two ways:

* If the imported rainfall data is a running total then `wee_import` can derive the WeeWX `rain` field from successive totals. For this method use `rain = cumulative`.

* If the imported rainfall data is a discrete value per date-time period then `rain = discrete` should be used.

!!! Note
    `wee_import` only supports cumulative rainfall data that resets on a
    midnight boundary, cumulative rainfall data that resets at some other
    time; e.g., 9am, is not supported. In such cases the rainfall data will
    need to be converted to either reset on a midnight boundary or a discrete
    value per date-time period and `rain = discrete` used. The former may be
    possible by selecting another rainfall field (if available) in the source
    data, otherwise it will require manual manipulation of the source data.

#### `wind_direction`{#csv_wind_direction}

WeeWX records wind direction in degrees as a number from 0 to 360 inclusive (no wind direction is recorded as `None/null`), whereas some data sources may provide wind direction as number over a different range (e.g., -180 to +180) or may use a particular value when there is no wind direction (e.g., 0 may represent no wind direction and 360 may represent a northerly wind, or -9999 (or some similar clearly invalid number) to represent there being no wind direction). `wee_import` handles such variations in data by defining a range over which imported wind direction values are accepted. Any value outside of this range is treated as there being no wind direction and is recorded as `None/null`. Any value inside the range is normalised to the range 0 to 360 inclusive (e.g., -180 would be normalised to 180). The `wind_direction` option consists of two comma separated numbers of the format lower, upper where lower and upper are inclusive. The operation of the `wind_direction` option is best illustrated through the following table:

<table id='wind_direction' class="indent" style="width:80%;text-align: center">
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

#### `[[FieldMap]]`{#csv_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the source data fields to WeeWX archive fields. The map consists of one row per field being imported using either of the following formats:

```
weewx_archive_field_name = csv_field_name, weewx_unit_name
```

or

```
weewx_archive_field_name = csv_field_name, text
```

Where:

* `weewx_archive_field_name` is a field name in the in-use WeeWX archive table schema
* `csv_field_name` is the name of a field from the CSV file
* `weewx_unit_name` is the WeeWX unit name of the units used by `csv_field_name`
* `text` is the literal word text

This mapping allows `wee_import` to take a source data field, do the appropriate unit conversion and store the resulting value in the appropriate WeeWX archive field. Source data text fields may be mapped to a WeeWX text archive field by using the second form of the field map entry where the literal `text` is used in place of a WeeWX unit name. A mapping is not required for every WeeWX archive field (e.g., the source may not provide inside temperature so no `inTemp` field mapping is required) and neither does every CSV field need to be included in a mapping (e.g., the source data field `monthrain` may have no use if the source data field `rain` provides the data for the WeeWX archive `rain field). Unused field mapping lines will not be used and may be omitted.

!!! Note
    Importing of text data into text fields in the WeeWX archive is only supported for WeeWX archive fields that have been configured as text fields. Refer to the Wiki page [Storing text in the database](https://github.com/weewx/weewx/wiki/Storing-text-in-the-database) for details.

If the source data includes a field that contains a WeeWX unit system code (i.e. the equivalent of the WeeWX `usUnits` field such as may be obtained from WeeWX or wview data) then this field can be mapped to the WeeWX `usUnits` field and used to set the units used for all fields being imported. In such cases the `weewx_unit_name` portion of the imported fields in the field map is not used and can be omitted.

For example, source CSV data with the following structure:

```
date_and_time,temp,humid,wind,dir,rainfall,rad,river
23 May 2018 13:00,17.4,56,3.0,45,0.0,956,340
23 May 2018 13:05,17.6,56,1.0,22.5,0.4,746,341
```

where `temp` is temperature in Celsius, `humid` is humidity in percent, `wind` is wind speed in km/h, `dir` is wind direction in degrees, `rainfall` is rain in mm, `rad` is radiation in watts per square meter and `river` is river height in mm might use a field map as follows:

```
[[FieldMap]]
    dateTime    = date_and_time, unix_epoch
    outTemp     = temp, degree_C
    outHumidity = humid, percent
    windSpeed   = wind, km_per_hour
    windDir     = dir, degree_compass
    rain        = rainfall, mm
    radiation   = rad, watt_per_meter_squared
```

If the same source CSV data included a field `unit_info` that contains WeeWX unit system data as follows:

```
date_and_time,temp,humid,wind,dir,rainfall,rad,river,unit_info
23 May 2018 13:00,17.4,56,3.0,45,0.0,956,340,1
23 May 2018 13:05,17.6,56,1.0,22.5,0.4,746,341,16
```

then a field map such as the following might be used:

```
[[FieldMap]]
    dateTime    = date_and_time, unix_epoch
    usUnits     = unit_info
    outTemp     = temp
    outHumidity = humid
    windSpeed   = wind
    windDir     = dir
    rain        = rainfall
    radiation   = rad
```

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for which there is no field mapping may be calculated during import by use of the [`calc_missing`](#csv_calc_missing) option in the `[CSV]` section of the import configuration file.

!!! Note
    The `dateTime` field map entry is a special case. Whereas other field map entries may use any supported WeeWX unit name, or no unit name if the `usUnits` field is populated, the `dateTime` field map entry must include the WeeWX unit name `unix_epoch`. This is because `wee_import` uses the [raw_datetime_format](#csv_raw_datetime_format) config option to convert the supplied date-time field data to a Unix epoch timestamp before the field map is applied.


### [WU]

The `[WU]` section contains the options relating to the import of observational data from a Weather Underground PWS history.

#### `station_id`{#wu_station_id}

The Weather Underground weather station ID of the PWS from which the historical data will be imported. 

There is no default.

#### `api_key`{#wu_api_key}

The Weather Underground API key to be used to obtain the PWS history data.

There is no default.

!!! Note
    The API key is a seemingly random string of 32 characters used to access the new (2019) Weather Underground API. PWS contributors can obtain an API key by logging onto the Weather Underground internet site and accessing Member Settings. 16 character API keys used with the previous Weather Underground API are not supported.

#### `interval`{#wu_interval}

Determines how the time interval (WeeWX database field `interval`) between successive observations is determined. This option is identical in operation to the CSV [interval](#csv_interval) option but applies to Weather Underground imports only. As a Weather Underground PWS history sometimes has missing records, the use of `interval = derive` may give incorrect or inconsistent interval values. Better results may be obtained by using `interval = conf` if the current WeeWX installation has the same `archive_interval` as the Weather Underground data, or by using `interval = x` where `x` is the time interval in minutes used to upload the Weather Underground data. The most appropriate setting will depend on the completeness and (time) accuracy of the Weather Underground data being imported.

The default is `derive`.

#### `qc`{#wu_qc}

Determines whether simple quality control checks are applied to imported data. This option is identical in operation to the CSV [qc](#csv_qc) option but applies to Weather Underground imports only. As Weather Underground imports at times contain nonsense values, particularly for fields for which no data was uploaded to Weather Underground by the PWS, the use of quality control checks on imported data can prevent these nonsense values from being imported and contaminating the WeeWX database.

The default is `True`.

#### `calc_missing`{#wu_calc_missing}

Determines whether any missing derived observations will be calculated from the imported data. This option is identical in operation to the CSV [calc_missing](#csv_calc_missing)" option but applies to Weather Underground imports only.

The default is `True`.

#### `ignore_invalid_data`{#wu_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import aborted. This option is identical in operation to the CSV [ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Weather Underground imports only. The default is `True`.

#### `tranche`{#wu_tranche}

The number of records written to the WeeWX database in each transaction. This option is identical in operation to the CSV [tranche](#csv_tranche) option but applies to Weather Underground imports only.

The default is `250` which should suit most users.

#### `wind_direction`{#wu_wind_direction}

Determines the range of acceptable wind direction values in degrees. This option is identical in operation to the CSV [wind_direction](#csv_wind_direction) option but applies to Weather Underground imports only.

The default is `0, 360` which should suit most users.


### [Cumulus]

The `[Cumulus]` section contains the options relating to the import of observational data from Cumulus monthly log files.

#### `directory`{#cumulus_directory}

The full path to the directory containing the Cumulus monthly log files to be imported. Do not include a trailing `/`. 

There is no default.

#### `source_encoding`{#cumulus_encoding}

The Cumulus monthly log file encoding. This option is identical in operation to the CSV [source_encoding](#csv_encoding) option but applies to Cumulus imports only.

The default is `utf-8-sig`.

#### `interval`{#cumulus_interval}

Determines how the time interval (WeeWX database field `interval`) between successive observations is determined. This option is identical in operation to the CSV [interval](#csv_interval) option but applies to Cumulus monthly log file imports only. As Cumulus monthly log files can, at times, have missing entries, the use of `interval = derive` may give incorrect or inconsistent interval values. Better results may be obtained by using `interval = conf` if the `archive_interval` for the current WeeWX installation is the same as the Cumulus 'data log interval' setting used to generate the Cumulus monthly log files, or by using `interval = x` where `x` is the time interval in minutes used as the Cumulus 'data log interval' setting. The most appropriate setting will depend on the completeness and (time) accuracy of the Cumulus data being imported.

The default is `derive`.

#### `qc`{#cumulus_qc}

Determines whether simple quality control checks are applied to imported data. This option is identical in operation to the CSV [qc](#csv_qc) option but applies to Cumulus imports only.

The default is `>True`.

#### `calc_missing`{#cumulus_calc_missing}

Determines whether any missing derived observations will be calculated from the imported data. This option is identical in operation to the CSV [calc_missing](#csv_calc_missing) option but applies to Cumulus imports only.

The default is `True`.

#### `separator`{#cumulus_separator}

The character used as the date field separator in the Cumulus monthly log file. A solidus (/) is frequently used, but it may be another character depending on the settings on the machine that produced the Cumulus monthly log files. This parameter must be included in quotation marks.

Default is `/`.

#### `delimiter`{#cumulus_delimiter}

The character used as the field delimiter in the Cumulus monthly log file. A comma is frequently used, but it may be another character depending on the settings on the machine that produced the Cumulus monthly log files. This parameter must be included in quotation marks.

Default is `,`.

#### `decimal`{#cumulus_decimal}

The character used as the decimal point in the Cumulus monthly log files. A full stop is frequently used, but it may be another character depending on the settings on the machine that produced the Cumulus monthly log files. This parameter must be included in quotation marks.

Default is `.`.

#### `ignore_invalid_data`{#cumulus_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import aborted. This option is identical in operation to the CSV [ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Cumulus monthly log file imports only.

The default is `True`.

#### `tranche`{#cumulus_tranche}

The number of records written to the WeeWX database in each transaction. This option is identical in operation to the CSV [tranche](#csv_tranche) option but applies to Cumulus monthly log file imports only.

The default is `250` which should suit most users.

#### `UV_sensor`{#cumulus_UV}

Enables `wee_import` to distinguish between the case where a UV sensor is present and the UV index is 0 and the case where no UV sensor is present and UV index is 0. This option is identical in operation to the CSV [UV_sensor](#csv_UV) option but applies to Cumulus monthly log file imports only.

The default is `True`.

#### `solar_sensor`{#cumulus_solar}

Enables `wee_import` to distinguish between the case where a solar radiation sensor is present and the solar radiation is 0 and the case where no solar radiation sensor is present and solar radiation is 0. This option is identical in operation to the CSV [solar_sensor](#csv_solar) option but applies to Cumulus monthly log file imports only.

The default is `True`.

#### `[[Units]]`{#cumulus_units}

The `[[Units]]` stanza defines the units used in the Cumulus monthly log files. Units settings are required for `temperature`, `pressure`, `rain` and `speed`. The format for each setting is:

```
obs_type = weewx_unit_name
```

Where `obs_type` is one of `temperature`, `pressure`, `rain` or `speed` and `weewx_unit_name` is the WeeWX unit name of the units used by that particular `obs_type`. As Cumulus supports a different suite of possible units only a subset of the available WeeWX unit names can be used for some settings.


### [WD]

The `[WD]` section contains the options relating to the import of observational data from Weather Display monthly log files.

#### `directory`{#wd_directory}

The full path to the directory containing the Weather Display monthly log files to be imported. Do not include a trailing `/`.

There is no default.

#### `logs_to_process`{#wd_logs_to_process}

The Weather Display monthly log files to be processed. Weather Display uses multiple files to record each month of data. Which monthly log files are produced depends on the Weather Display configuration and the capabilities of the weather station. `wee_import` supports the following Weather Display monthly log files:

* MMYYYYlg.txt
* MMYYYYlgcsv.csv (csv format version of MMYYYYlg.txt)
* MMYYYYvantagelog.txt
* MMYYYYvantagelogcsv.csv (csv format version of MMYYYYvantagelog.txt)
* MMYYYYvantageextrasensorslog.csv

where MM is a one or two-digit month and YYYY is a four digit year

The format for the `logs_to_process` setting is:

```
logs_to_process = [lg.txt, | logcsv.csv, | vantagelog.txt, | vantagelogcsv.csv, | vantageextrasensorslog.csv]
```

!!! Note
    The leading MMYYYY is omitted when listing the monthly log files to be processed using the `logs_to_process` setting. Inclusion of the leading MMYYYY will cause the import to fail.

!!! Note
    The MMYYYYlgcsv.csv and MMYYYYvantagelogcsv.csv log files are CSV versions of MMYYYYlg.txt and MMYYYYvantagelog.txt respectively. Either the .txt or .csv version of these files should be used but not both.

The monthly log files selected for processing should be chosen carefully as the selected log files will determine the Weather Display data fields available for import. `wee_import` is able to import the following data from the indicated monthly log files:

* MMYYYYlg.txt/MMYYlgcsv.csv:
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

* MMYYYYvantagelog.txt/MMYYYYvantagelogcsv.csv:
    * `date and time`
    * `soil moisture`
    * `soil temperature`
    * `solar radiation`
    * `UV index`

* MMYYYYvantageextrasensorslog.csv:
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
    Whilst the above log files may contain the indicated data the data may only be imported subject to a suitable field map and in-use WeeWX archive table schema (refer to the [[[FieldMap]]](#wd_fieldmap) option).

The default is `lg.txt, vantagelog.txt, vantageextrasensorslog.csv`.

#### `source_encoding`{#wd_encoding}

The Weather Display monthly log file encoding. This option is identical in operation to the CSV [source_encoding](#csv_encoding) option but applies to Weather Display imports only.

The default is `utf-8-sig`.

#### `interval`{#wd_interval}

Determines how the time interval (WeeWX database field `interval`) between successive observations is determined. This option is identical in operation to the CSV [interval](#csv_interval) option but applies to Weather Display monthly log file imports only. As Weather Display log files nominally have entries at one minute intervals the recommended approach is to set `interval = 1`. As Weather Display monthly log files can, at times, have missing entries, the use of `interval = derive` may give incorrect or inconsistent interval values. If then `archive_interval` for the current WeeWX installation is 1 minute `interval = conf` may be used. In most cases the most appropriate setting will be `interval = 1`.

The default is `1`.

#### `qc`{#wd_qc}

Determines whether simple quality control checks are applied to imported data. This option is identical in operation to the CSV [qc](#csv_qc) option but applies to Weather Display imports only.

The default is `True`.

#### `calc_missing`{#wd_calc_missing}

Determines whether any missing derived observations will be calculated from the imported data. This option is identical in operation to the CSV [calc_missing](#csv_calc_missing) option but applies to Weather Display imports only.

The default is `True`.

#### `txt_delimiter`{#wd_txt_delimiter}

The character used as the field delimiter in Weather Display text format monthly log files (.txt files). A space is normally used but another character may be used if necessary. This parameter must be included in quotation marks.

The default is `' '`.

#### `csv_delimiter`{#wd_csv_delimiter}

The character used as the field delimiter in Weather Display csv format monthly log files (.csv files). A comma is normally used but another character may be used if necessary. This parameter must be included in quotation marks. Default is `,`.

#### `decimal`{#wd_decimal}

The character used as the decimal point in the Weather Display monthly log files. A full stop is frequently used but another character may be used if necessary. This parameter must be included in quotation marks.

The default is `.`.

#### `ignore_missing_log`{#wd_ignore_missing_log}

Determines whether missing log files are to be ignored or the import aborted. Weather Display log files are complete in themselves and a missing log file will have no effect other than there will be no imported data for the period covered by the missing log file. The default is `True`.

#### `ignore_invalid_data`{#wd_ignore_invalid_data}

Determines whether invalid data in a source field is ignored or the import aborted. This option is identical in operation to the CSV [ignore_invalid_data](#csv_ignore_invalid_data) option but applies to Weather Display monthly log file imports only.

The default is `True`.

#### `tranche`{#wd_tranche}

The number of records written to the WeeWX database in each transaction. This option is identical in operation to the CSV [tranche](#csv_tranche) option but applies to Weather Display monthly log file imports only.

The default is `250` which should suit most users.

#### `UV_sensor`{#wd_UV}

Enables `wee_import` to distinguish between the case where a UV sensor is present and the UV index is 0 and the case where no UV sensor is present and UV index is 0. This option is identical in operation to the CSV [UV_sensor](#csv_UV) option but applies to Weather Display monthly log file imports only.

The default is `True`.

#### `solar_sensor`{#wd_solar}

Enables `wee_import` to distinguish between the case where a solar radiation sensor is present and the solar radiation is 0 and the case where no solar radiation sensor is present and solar radiation is 0. This option is identical in operation to the CSV [solar_sensor](#csv_solar) option but applies to Weather Display monthly log file imports only.

The default is `True`.

#### `ignore_extreme_temp_hum`{#wd_ignore_extreme_temp_hum}

Determines whether extreme temperature and humidity values are ignored. Weather Display log files record the value 255 for temperature and humidity fields if no corresponding sensor is present. Setting `ignore_extreme_temp_hum = True` will cause temperature and humidity values of 255 to be ignored. Setting `ignore_extreme_temp_hum = False` will cause temperature and humidity values of 255 to be treated as valid data to be imported.

The default is `True`.

!!! Note
    Setting `ignore_extreme_temp_hum = False` will cause temperature and humidity values of 255 to be imported; however, these values may be rejected by the simple quality control checks implemented if `qc = True` is used.

#### `[[Units]]`{#wd_units}

The `[[Units]]` stanza defines the units used in the Weather Display monthly log files. Weather Display monthly log files normally use Metric or US customary units depending on the _Log File_ setting under _Units_ on the _Units/Wind Chill_ tab of the Weather Display _Universal Setup_. In such cases the `units` configuration option may be set to `Metric` or `US` to select either Metric or US customary units.

There is no default.

It is also possible to individually specify the log file units used for `temperature`, `pressure`, `rain` and `speed`. The format for each setting is:

```
obs_type = weewx_unit_name
```

Where `obs_type` is one of `temperature`, `pressure`, `rain` or `speed` and `weewx_unit_name is the WeeWX unit name of the units used by that particular `obs_type. As Weather Display supports a different suite of possible units only a subset of the available WeeWX unit names can be used for some settings.

The preferred method for defining the Weather Display log file units is through the use of the `units` configuration option. When defining the import log file units either the `units` configuration option should be used or the individual `temperature`, `pressure`, `rain` and `>speed` units defined but not both. If both the `units` configuration option is defined as well as the individual `temperature`, `pressure`, `rain` and `speed` units defined the `units` configuration option takes precedence and all other units settings are ignored.

#### `[[FieldMap]]`{#wd_fieldmap}

The `[[FieldMap]]` stanza defines the mapping from the Weather Display monthly log data fields to WeeWX archive fields. By default, imported Weather Display data is mapped to the corresponding WeeWX archive fields using a default field map. The default field map will likely suit most users; however, depending on the station capabilities and the in-use WeeWX database schema, a custom field map may be required if Weather Display monthly logs contain data from additional sensors that cannot be stored in the WeeWX archive using the default field map. A custom field map also makes it possible to limit the Weather Display monthly log data fields that are imported into WeeWX.

The field map consists of one row per field using the format:

```
weewx_archive_field_name = weather_display_field_name
```

Where `weewx_archive_field_name` is a field name in the in-use WeeWX archive table schema and `weather_display_field_name` is a Weather Display import field name. The available Weather Display import field names are listed in the table below.

<table id="wd-avail-import-field-names-table" class="indent">
    <caption>Available import field names</caption>
    <tbody>
    <tr class="first_row">
        <td>Field name</td>
        <td>Description</td>
    </tr>
    <tr>
        <td class="first_col code">barometer</td>
        <td>barometric pressure</td>
    </tr>
    <tr>
        <td class="first_col code">dewpoint</td>
        <td>dew point</td>
    </tr>
    <tr>
        <td class="first_col code">direction</td>
        <td>wind direction</td>
    </tr>
    <tr>
        <td class="first_col code">gustspeed</td>
        <td>wind gust speed</td>
    </tr>
    <tr>
        <td class="first_col code">heatindex</td>
        <td>heat index</td>
    </tr>
    <tr>
        <td class="first_col code">humidity</td>
        <td>outside humidity</td>
    </tr>
    <tr>
        <td class="first_col code">hum1</td>
        <td>extra humidity 1</td>
    </tr>
    <tr>
        <td class="first_col code">hum2</td>
        <td>extra humidity 2</td>
    </tr>
    <tr>
        <td class="first_col code">hum3</td>
        <td>extra humidity 3</td>
    </tr>
    <tr>
        <td class="first_col code">hum4</td>
        <td>extra humidity 4</td>
    </tr>
    <tr>
        <td class="first_col code">hum5</td>
        <td>extra humidity 5</td>
    </tr>
    <tr>
        <td class="first_col code">hum6</td>
        <td>extra humidity 6</td>
    </tr>
    <tr>
        <td class="first_col code">radiation</td>
        <td>solar radiation</td>
    </tr>
    <tr>
        <td class="first_col code">rainlastmin</td>
        <td>rainfall in the last 1 minute</td>
    </tr>
    <tr>
        <td class="first_col code">soilmoist</td>
        <td>soil moisture</td>
    </tr>
    <tr>
        <td class="first_col code">soiltemp</td>
        <td>soil temperature</td>
    </tr>
    <tr>
        <td class="first_col code">temperature</td>
        <td>outside temperature</td>
    </tr>
    <tr>
        <td class="first_col code">temp1</td>
        <td>extra temperature 1</td>
    </tr>
    <tr>
        <td class="first_col code">temp2</td>
        <td>extra temperature 2</td>
    </tr>
    <tr>
        <td class="first_col code">temp3</td>
        <td>extra temperature 3</td>
    </tr>
    <tr>
        <td class="first_col code">temp4</td>
        <td>extra temperature 4</td>
    </tr>
    <tr>
        <td class="first_col code">temp5</td>
        <td>extra temperature 5</td>
    </tr>
    <tr>
        <td class="first_col code">temp6</td>
        <td>extra temperature 6</td>
    </tr>
    <tr>
        <td class="first_col code">uv</td>
        <td>UV index</td>
    </tr>
    <tr>
        <td class="first_col code">windspeed</td>
        <td>average wind speed</td>
    </tr>
    </tbody>
</table>

A mapping is not required for every WeeWX archive field (e.g., the Weather Display monthly logs may not provide inside temperature so no `inTemp` field mapping is required) and neither does every Weather Display monthly log field need to be included in a mapping (e.g., the Weather Display monthly log field `soiltemp` may have no data as the station has no soil temperature probe).

!!! Note
    Any WeeWX archive fields that are derived (e.g., `dewpoint`) and for which there is no field mapping may be calculated during import by use of the `calc_missing` option in the `[WD]` section of the import configuration file.

The example Weather Display import configuration file located in the `/home/weewx/util/import]` or the `/etc/weewx/import directory contains an example field map in the import configuration file comments. There is no default.


### [WeatherCat]

The `[WeatherCat]` section contains the options relating to the import of observational data from WeatherCat monthly .cat files.

#### `directory`{#wcat_directory}

The full path to the directory containing the year directories that contain the WeatherCat monthly .cat files to be imported. Do not include a trailing `/`.

There is no default.

#### `source_encoding`{#wcat_encoding}

The WeatherCat monthly .cat file encoding. This option is identical in operation to the CSV [source_encoding](#csv_encoding) option but applies to WeatherCat imports only.

The default is `utf-8-sig`.

#### `interval`{#wcat_interval}

Determines how the time interval (WeeWX database field `interval`) between successive observations is determined. This option is identical in operation to the CSV [interval](#csv_interval) option but applies to WeatherCat imports only. As WeatherCat monthly .cat files can, at times, have missing entries, the use of `interval = derive` may give incorrect or inconsistent interval values. Better results may be obtained by using `interval = conf` if the `archive_interval` for the current WeeWX installation is the same as the WeatherCat .cat file log interval, or by using `interval = x` where `x` is the time interval in minutes used in the WeatherCat monthly .cat file(s). The most appropriate setting will depend on the completeness and (time) accuracy of the WeatherCat data being imported.

The default is `derive`.

#### `qc`{#wcat_qc}

Determines whether simple quality control checks are applied to imported data. This option is identical in operation to the CSV [qc](#csv_qc) option but applies to WeatherCat imports only.

The default is `True`.

#### `calc_missing`{#wcat_calc_missing}

Determines whether any missing derived observations will be calculated from the imported data. This option is identical in operation to the CSV [calc_missing](#csv_calc_missing) option but applies to WeatherCat imports only.

The default is `True`.

#### `decimal`{#wcat_decimal}

The character used as the decimal point in the WeatherCat monthly .cat files. This parameter must be included in quotation marks.

The default is `.`.

#### `tranche`{#wcat_tranche}

The number of records written to the WeeWX database in each transaction. This option is identical in operation to the CSV [tranche](#csv_tranche) option but applies to WeatherCat imports only.

The default is `250` which should suit most users.

#### `UV_sensor`{#wcat_UV}

Enables `wee_import` to distinguish between the case where a UV sensor is present and the UV index is 0 and the case where no UV sensor is present and UV index is 0. This option is identical in operation to the CSV [UV_sensor](#csv_UV) option but applies to WeatherCat imports only.

The default is `True`.

#### `solar_sensor`{#wcat_solar}

Enables `wee_import` to distinguish between the case where a solar radiation sensor is present and the solar radiation is 0 and the case where no solar radiation sensor is present and solar radiation is 0. This option is identical in operation to the CSV [solar_sensor](#csv_solar) option but applies to WeatherCat imports only.

The default is `True`.

#### `[[Units]]`{#wcat_units}

The `[[Units]]` stanza defines the units used in the WeatherCat monthly .cat files. Unit settings are required for `temperature`, `pressure`, `rain` and `speed`. The format for each setting is:

```
obs_type = weewx_unit_name
```

Where `obs_type` is one of `temperature`, `pressure`, `rain` or `speed` and `weewx_unit_name` is the WeeWX unit name of the units used by that particular `obs_type` (refer to the [_Units_](../../reference/units) for details of available WeeWX unit names). As WeatherCat supports a different suite of possible units only a subset of the available WeeWX unit names can be used for some settings.
