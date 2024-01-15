!!! Warning
    Running WeeWX during a `weectl import` session can lead to abnormal 
    termination of the import. If WeeWX must remain running (e.g., so that 
    live data is not lost) run the `weectl import` session on another machine 
    or to a second database and merge the in-use and second database once the 
    import is complete.

`weectl import` can import data from a single CSV file. The CSV source file 
must be structured as follows:

* The file must have a header row consisting of a comma separated list of 
  field names. The field names can be any valid string as long as each field 
  name is unique within the list. There is no requirement for the field names 
  to be in any particular order as long as the same order is used for the 
  observations on each row in the file. These field names will be mapped to 
  WeeWX field names in the `[CSV]` section of the import configuration file.

* Observation data for a given date-time must be listed on a single line with 
  individual fields separated by a comma. The fields must be in the same 
  order as the field names in the header row.

* Blank fields are represented by the use of white space or no space only 
  between commas.

* Direction data being imported may be represented as numeric degrees or 
  as a string representing the [cardinal, intercardinal and/or secondary 
  intercardinal directions](https://en.wikipedia.org/wiki/Cardinal_direction).

* There must a field that represents the date-time of the observations on 
  each line. This date-time field must be either a Unix epoch timestamp or 
  any date-time format that can be represented using [Python strptime() 
  format codes](https://docs.python.org/2/library/datetime.
  html#strftime-and-strptime-behavior).

A CSV file suitable for import by `weectl import` may look like this:

```
Time,Barometer,Temp,Humidity,Windspeed,Dir,Gust,Dayrain,Radiation,Uv,Comment
28/11/2017 08:00:00,1016.9,24.6,84,1.8,113,8,0,359,3.8,"start of observations"
28/11/2017 08:05:00,1016.9,25.1,82,4.8,135,11.3,0,775,4.7,
28/11/2017 08:10:00,1016.9,25.4,80,4.4,127,11.3,0,787,5.1,"note temperature"
28/11/2017 08:15:00,1017,25.7,79,3.5,74,11.3,0,800,5.4,
28/11/2017 08:20:00,1016.9,25.9,79,1.6,95,9.7,0,774,5.5,
28/11/2017 08:25:00,1017,25.5,78,2.9,48,9.7,0,303,3.4,"forecast received"
28/11/2017 08:30:00,1017.1,25.1,80,3.1,54,9.7,0,190,3.6,
```

or this:

```
Time,Barometer,Temp,Humidity,Windspeed,Dir,Gust,Dayrain,Radiation,Uv
2/1/2017 06:20:00,1006.4,4.8,48,2.8,NE,4,0,349,2.8
2/1/2017 06:25:00,1006.9,5.0,48,3.8,NNE,21.3,0,885,4.3
2/1/2017 06:30:00,1006.8,5.4,47,3.4,North,12.3,0,887,5.3
2/1/2017 06:35:00,1007,5.2,49,5.5,NNE,13.3,0,600,5.4
2/1/2017 06:40:00,1006.9,5.7,49,2.6,ESE,9.7,0,732,5.5
2/1/2017 06:45:00,1007,5.5,48,1.9,Southsoutheast,9.8,0,393,6.4
2/1/2017 06:50:00,1007.1,5.2,50,2.1,southeast,9.9,0,180,6.6
```

!!! Note
    [Cardinal, intercardinal and/or secondary intercardinal directions](https://en.wikipedia.org/wiki/Cardinal_direction) 
    may be represented by one, two or three letter abbreviations e.g., N, SE 
    or SSW; by a single word e.g., North, Southwest or Southsouthwest or 
    by hyphenated or spaced words e.g., North West or South-south-west. 
    Capitalisation is ignored as are any spaces, hyphens or other white 
    space. At present only English abbreviations and directions are supported.

## Mapping data to archive fields

The WeeWX archive fields populated during a CSV import depend on the 
CSV-to-WeeWX field mappings specified in `[[FieldMap]]` stanza in the import 
configuration file. If a valid field mapping exists, the WeeWX field exists 
in the WeeWX archive table schema and provided the mapped CSV field contains 
valid data, the corresponding WeeWX field will be populated.

!!! Note
    The use of the [calc_missing](weectl-import-config-opt.md#csv_calc_missing) 
    option in the import configuration file may result in a number of derived 
    fields being calculated from the imported data. If these derived fields 
    exist in the in-use database schema they will be saved to the database as 
    well.

## Step-by-step instructions

To import observations from a CSV file:

1. Ensure the source data file is in a directory accessible by the machine 
   that will run `weectl import`. For the purposes of the following examples 
   the source data file `data.csv` located in the `/var/tmp` directory 
   will be used.

2. Make a backup of the WeeWX database in case the import should go awry.

3. Create an import configuration file. In this case we will make a copy of 
   the example CSV import configuration file and save it as `csv.conf` in the 
   `/var/tmp` directory:

    ```
    cp /home/weewx/util/import/csv-example.conf /var/tmp/csv.conf
    ```
   
4. Confirm that the [`source`](weectl-import-config-opt.md#import_config_source) 
   option is set to CSV:
 
    ```
    source = CSV
    ```

5. Confirm the following options in the `[CSV]` section are set:

    * [file](weectl-import-config-opt.md#csv_file). The full path and 
   file 
name of the file containing the CSV formatted data to be imported.

    * [delimiter](weectl-import-config-opt.md#csv_delimiter). The single 
    character used to separate fields.

    * [interval](weectl-import-config-opt.md#csv_interval). Determines how 
      the 
    WeeWX interval field is derived.

    * [qc](weectl-import-config-opt.md#csv_qc). Determines whether quality 
    control checks are performed on the imported data.

    * [calc_missing](weectl-import-config-opt.md#csv_calc_missing). 
      Determines 
    whether missing derived observations will be calculated from the imported 
    data.

    * [ignore_invalid_data](weectl-import-config-opt.md#csv_ignore_invalid_data).
    Determines whether invalid data in a source field is ignored or the import 
    aborted.

    * [tranche](weectl-import-config-opt.md#csv_tranche). The number of 
     records 
    written to the WeeWX database in each transaction.

    * [UV_sensor](weectl-import-config-opt.md#csv_UV). Whether a UV sensor 
      was 
    installed when the source data was produced.

    * [solar_sensor](weectl-import-config-opt.md#csv_solar). Whether a solar 
    radiation sensor was installed when the source data was produced.

    * [raw_datetime_format](weectl-import-config-opt.md#csv_raw_datetime_format).
    The format of the imported date time field.

    * [rain](weectl-import-config-opt.md#csv_rain). Determines how the 
     WeeWX rain 
    field is derived.
       
    * [wind_direction](weectl-import-config-opt.md#csv_wind_direction). 
    Determines how imported wind direction fields are interpreted.

    * [[[FieldMap]]](weectl-import-config-opt.md#csv_fieldmap). Defines the 
    mapping between imported data fields and WeeWX archive fields. Also defines 
    the units of measure for each imported field.

6. When first importing data it is prudent to do a dry run import before any 
   data are actually imported. A dry run import will perform all steps of the 
   import without actually writing imported data to the WeeWX database. In 
   addition, consideration should be given to any additional options such 
   as `--date`.

    To perform a dry run enter the following command:

    ```
    weectl import --import-config=/var/tmp/csv.conf --dry-run
    ```

    The output should be something like:

    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    A CSV import from source file '/var/tmp/data.csv' has been requested.
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    This is a dry run, imported data will not be saved to archive.
    Starting dry run import ...
    27337 records identified for import.
    Unique records processed: 27337; Last timestamp: 2018-03-03 06:00:00 AEST (1520020800)
    Finished dry run import
    27337 records were processed and 27337 unique records would have been imported.
    ```

    The output includes details about the data source, the destination of the 
    imported data and some other details on how the data will be processed. 
    The import will then be performed but no data will be written to the 
    WeeWX database. Upon completion a brief summary of the records processed 
    is provided.

7. Once the dry run results are satisfactory the data can be imported using 
   the following command:

    ```
    weectl import --import-config=/var/tmp/csv.conf
    ```

    This will result in a short preamble similar to that from the dry run. At 
    the end of the preamble there will be a prompt:

    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    A CSV import from source file '/var/tmp/data.csv' has been requested.
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    Starting import ...
    27337 records identified for import.
    Proceeding will save all imported records in the WeeWX archive.
    Are you sure you want to proceed (y/n)?
    ```

8. If the import parameters are acceptable enter `y` to proceed with the 
   import or `n` to abort the import. If the import is confirmed the source 
   data will be imported, processed and saved in the WeeWX database.
   Information on the progress of the import will be displayed similar to the 
   following:

    ```
    Unique records processed: 3250; Last timestamp: 2017-12-09 14:45:00 AEST (1512794700)
    ```

    The line commencing with `Unique records processed` should update as 
    records are imported with progress information on number of records 
    processed, number of unique records imported and the date time of the 
    latest record processed. Once the initial import is complete 
    `weectl import` will, if requested, calculate any missing derived 
    observations and rebuild the daily summaries. A brief summary should be 
    displayed similar to the following:

    ```
    Calculating missing derived observations...
    Processing record: 27337; Last record: 2018-03-03 06:00:00 AEST (1520020800)
    Recalculating daily summaries...
    Records processed: 27337; Last date: 2018-03-03 06:00:00 AEST (1520020800)
    Finished recalculating daily summaries
    Finished calculating missing derived observations
    ```
    
    When the import is complete a brief summary is displayed similar to the 
    following:
    
    ```
    Finished import
    27337 records were processed and 27337 unique records imported in 113.91 seconds.
    Those records with a timestamp already in the archive will not have been
    imported. Confirm successful import in the WeeWX log file.
    ```

9. Whilst `weectl import` will advise of the number of records processed and 
   the number of unique records found, `weectl import` does know how many, if 
   any, of the imported records were successfully saved to the database. You 
   should look carefully through the WeeWX log file covering the `weectl 
   import` session and take note of any records that were not imported. The 
   most common reason for imported records not being saved to the database is 
   because a record with that timestamp already exists in the database, in 
   such cases something similar to the following will be found in the log:

    ```
    2023-11-04 15:33:01 weectl-import[3795]: ERROR weewx.manager: Unable to add record 2018-09-04 04:20:00 AEST (1535998800) to database 'weewx.sdb': UNIQUE constraint failed: archive.dateTime
    ```
    
    In such cases you should take note of the timestamp of the record(s) 
    concerned and make a decision about whether to delete the pre-existing 
    record and re-import the record or retain the pre-existing record.
