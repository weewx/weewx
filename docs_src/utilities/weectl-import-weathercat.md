!!! Warning
    Running WeeWX during an `import` session can lead to abnormal termination 
    of the import. If WeeWX must remain running (e.g., so that live data is 
    not lost) run the `import` session on another machine or to a second 
    database and merge the in-use and second database once the import is 
    complete.

WeatherCat records observational data in formatted text files with a .cat 
extension with each file containing weather station observations for a single 
month. These files are accumulated over time with month coded files names 
organised into year based directories. These files can be considered 
analogous to the WeeWX archive table. When data is imported from the 
WeatherCat .cat files each .cat file is considered a 'period'. The `import` 
utility processes one period at a time in chronological order (oldest to 
newest) and provides import summary data on a per period basis.

## Mapping data to archive fields

The WeeWX archive fields populated during the import of WeatherCat data 
depends on the field mapping specified in the 
[`[[FieldMap]]`](weectl-import-config-opt.md#wcat_fieldmap) stanza in the 
import configuration file. A given WeeWX field will be populated if:

* a valid mapping exists for the field,
* the field exists in the WeeWX archive table schema, and
* the mapped WeatherCat field contains valid data.

The following WeeWX archive fields will be populated from other settings or 
configuration options and need not be included in the field map:

* `interval`
* `usUnits`

The following WeeWX archive fields will be populated with values derived from 
the imported data provided 
[`calc_missing = True`](weectl-import-config-opt.md#wcat_calc_missing) is 
included in the `[WeatherCat]` section of the import configuration file being 
used and the field exists in the in-use WeeWX archive table schema:

* `altimeter`
* `ET`
* `pressure`

!!! Note
    If `calc_missing = False` is included in the `[WeatherCat]` section of 
    the import configuration file being used then all of the above fields
    will be set to `None/null`. The `calc_missing` option default is `True`.


## Step-by-step instructions

To import observations from one or more WeatherCat monthly .cat files:

1. Ensure the WeatherCat monthly .cat file(s) to be used for the import are 
   located in year directories with the year directories in turn located in a 
   directory accessible by the machine that will run the `import` utility. 
   For the purposes of the following examples there are nine monthly .cat 
   files covering the period October 2016 to June 2017 inclusive located in 
   the `/var/tmp/wcat/2016` and `/var/tmp/wcat/2017` directories respectively.

2. Make a backup of the WeeWX database in case the import should go awry.

3. Create an import configuration file, the recommended approach is to make a 
   copy of the example WeatherCat import configuration file located in the 
   `util/import` directory. In this case we will make a copy of the example 
   WeatherCat import configuration file and save it as `wcat.conf` in the 
   `/var/tmp` directory:

    ```
    cp /home/weewx/www-data/util/import/weathercat-example.conf /var/tmp/wcat.conf
    ```

4. Open `wcat.conf` and:

    * confirm the [`source`](weectl-import-config-opt.md#import_config_source) 
      option is set to `WeatherCat`:

        ```
        source = WeatherCat
        ```

    * confirm the following options in the `[WeatherCat]` section are 
      correctly set:

        * [directory](weectl-import-config-opt.md#wcat_directory). The full
          path to the directory containing the directories containing the 
          WeatherCat monthly .cat files to be used as the source of the 
          imported data.
    
        * [interval](weectl-import-config-opt.md#wcat_interval). How the 
          WeeWX `interval` field is derived.
    
        * [qc](weectl-import-config-opt.md#wcat_qc). Whether quality control 
          checks are performed on the imported data.
    
        * [calc_missing](weectl-import-config-opt.md#wcat_calc_missing). 
          Whether missing derived observations will be calculated from the 
          imported data.
    
        * [decimal](weectl-import-config-opt.md#wcat_decimal). The decimal 
          point character used in the WeatherCat monthly .cat files.
    
        * [tranche](weectl-import-config-opt.md#wcat_tranche). The number of 
          records written to the WeeWX database in each transaction.
    
        * [UV_sensor](weectl-import-config-opt.md#wcat_UV). Whether a UV 
          sensor was installed when the source data was produced.
    
        * [solar_sensor](weectl-import-config-opt.md#wcat_solar). Whether a 
          solar radiation sensor was installed when the source data was 
          produced.
    
        * [[[FieldMap]]](weectl-import-config-opt.md#wcat_fieldmap). Defines 
          the mapping between imported data fields and WeeWX archive fields.

5. When first importing data it is prudent to do a dry run import before any 
   data is actually imported. A dry run import will perform all steps of the 
   import without actually writing imported data to the WeeWX database. In 
   addition, consideration should be given to any additional options to be 
   used such as `--date`.

    !!! Note
        Whilst WeatherCat monthly .cat files use a fixed set of fields the 
        inclusion of fields other than `t` (timestamp) and `V` (validation)
        is optional. For this reason the field map used for WeatherCat 
        imports includes fields that may not exist in some WeatherCat monthly 
        .cat files resulting in warnings by the `import` utility there may be 
        missing data in the import source. These warnings can be extensive 
        and may detract from the ability of the user to monitor the progress 
        of the import. It may be prudent to use the `--suppress-warnings` 
        option during the initial dry run so the overall progress of the 
        import can be more easily observed.

    To perform a dry run enter the following command:

    ```
    weectl import --import-config=/var/tmp/wcat.conf --dry-run --suppress-warnings
    ```

    This will result in a short preamble with details on the data source, the 
    destination of the imported data and some other details on how the data 
    will be processed. The import will then be performed but no data will be 
    written to the WeeWX database.
    
    The output should be similar to:
    
    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    WeatherCat monthly .cat files in the '/var/tmp/wcat' directory will be imported
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    This is a dry run, imported data will not be saved to archive.
    Starting dry run import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Unique records processed: 39555; Last timestamp: 2016-10-31 23:59:00 AEST (1477922340)
    Period 2 ...
    Unique records processed: 38284; Last timestamp: 2016-11-30 23:59:00 AEST (1480514340)
    Period 3 ...
    Unique records processed: 39555; Last timestamp: 2016-12-31 23:59:00 AEST (1483192740)
    Period 4 ...
    Unique records processed: 39555; Last timestamp: 2017-01-31 23:59:00 AEST (1485871140)
    Period 5 ...
    Unique records processed: 35598; Last timestamp: 2017-02-28 23:59:00 AEST (1488290340)
    Period 6 ...
    Unique records processed: 39555; Last timestamp: 2017-03-31 23:59:00 AEST (1490968740)
    Period 7 ...
    Unique records processed: 38284; Last timestamp: 2017-04-30 23:59:00 AEST (1493560740)
    Period 8 ...
    Unique records processed: 38284; Last timestamp: 2017-06-30 23:59:00 AEST (1498831140)
    Finished dry run import
    308670 records were processed and 308670 unique records would have been imported.
    ```
    
    !!! Note
        The eight periods correspond to the eight monthly .cat files used for 
        this import.
    
    !!! Note
        Any periods for which no data could be obtained will be skipped. The 
        lack of data may be due to a missing WeatherCat monthly .cat file. A 
        short explanatory note to this effect will be displayed against the 
        period concerned and an entry included in the log.

6. If the `--suppress-warnings` option was used it may be prudent to do a 
   second dry run this time without the `--suppress-warnings` option. This 
   will allow any warnings generated by the dry run import to be observed:

    ```
    weectl import --import-config=/var/tmp/wcat.conf --dry-run
    ```
    
    This will result in a short preamble with details on the data source, the 
    destination of the imported data and some other details on how the data 
    will be processed. The import will then be performed but no data will be 
    written to the WeeWX database.
    
    The output should be similar to:

    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    WeatherCat monthly .cat files in the '/var/tmp/wcat' directory will be imported
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    This is a dry run, imported data will not be saved to archive.
    Starting dry run import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Warning: Import field 'T1' is mapped to WeeWX field 'extraTemp1' but the
    import field 'T1' could not be found in one or more records.
    WeeWX field 'extraTemp1' will be set to 'None' in these records.
    Warning: Import field 'T2' is mapped to WeeWX field 'extraTemp2' but the
    import field 'T2' could not be found in one or more records.
    WeeWX field 'extraTemp2' will be set to 'None' in these records.
    Warning: Import field 'T3' is mapped to WeeWX field 'extraTemp3' but the
    import field 'T3' could not be found in one or more records.
    WeeWX field 'extraTemp3' will be set to 'None' in these records.
    Warning: Import field 'H1' is mapped to WeeWX field 'extraHumid1' but the
    import field 'H1' could not be found in one or more records.
    WeeWX field 'extraHumid1' will be set to 'None' in these records.
    Warning: Import field 'H2' is mapped to WeeWX field 'extraHumid2' but the
    import field 'H2' could not be found in one or more records.
    WeeWX field 'extraHumid2' will be set to 'None' in these records.
    Warning: Import field 'Sm1' is mapped to WeeWX field 'soilMoist1' but the
    import field 'Sm1' could not be found in one or more records.
    WeeWX field 'soilMoist1' will be set to 'None' in these records.
    Warning: Import field 'Sm2' is mapped to WeeWX field 'soilMoist2' but the
    import field 'Sm2' could not be found in one or more records.
    WeeWX field 'soilMoist2' will be set to 'None' in these records.
    Warning: Import field 'Sm3' is mapped to WeeWX field 'soilMoist3' but the
    import field 'Sm3' could not be found in one or more records.
    WeeWX field 'soilMoist3' will be set to 'None' in these records.
    Warning: Import field 'Sm4' is mapped to WeeWX field 'soilMoist4' but the
    import field 'Sm4' could not be found in one or more records.
    WeeWX field 'soilMoist4' will be set to 'None' in these records.
    Warning: Import field 'Lw1' is mapped to WeeWX field 'leafWet1' but the
    import field 'Lw1' could not be found in one or more records.
    WeeWX field 'leafWet1' will be set to 'None' in these records.
    Warning: Import field 'Lw2' is mapped to WeeWX field 'leafWet2' but the
    import field 'Lw2' could not be found in one or more records.
    WeeWX field 'leafWet2' will be set to 'None' in these records.
    Warning: Import field 'St1' is mapped to WeeWX field 'soilTemp1' but the
    import field 'St1' could not be found in one or more records.
    WeeWX field 'soilTemp1' will be set to 'None' in these records.
    Warning: Import field 'St2' is mapped to WeeWX field 'soilTemp2' but the
    import field 'St2' could not be found in one or more records.
    WeeWX field 'soilTemp2' will be set to 'None' in these records.
    Warning: Import field 'St3' is mapped to WeeWX field 'soilTemp3' but the
    import field 'St3' could not be found in one or more records.
    WeeWX field 'soilTemp3' will be set to 'None' in these records.
    Warning: Import field 'St4' is mapped to WeeWX field 'soilTemp4' but the
    import field 'St4' could not be found in one or more records.
    WeeWX field 'soilTemp4' will be set to 'None' in these records.
    Warning: Import field 'Lt1' is mapped to WeeWX field 'leafTemp1' but the
    import field 'Lt1' could not be found in one or more records.
    WeeWX field 'leafTemp1' will be set to 'None' in these records.
    Warning: Import field 'Lt2' is mapped to WeeWX field 'leafTemp2' but the
    import field 'Lt2' could not be found in one or more records.
    WeeWX field 'leafTemp2' will be set to 'None' in these records.
    Unique records processed: 39555; Last timestamp: 2016-10-31 23:59:00 AEST (1477922340)
    Period 2 ...
    Warning: Import field 'T1' is mapped to WeeWX field 'extraTemp1' but the
    import field 'T1' could not be found in one or more records.
    WeeWX field 'extraTemp1' will be set to 'None' in these records.
    Warning: Import field 'T2' is mapped to WeeWX field 'extraTemp2' but the
    import field 'T2' could not be found in one or more records.
    WeeWX field 'extraTemp2' will be set to 'None' in these records.
    Warning: Import field 'T3' is mapped to WeeWX field 'extraTemp3' but the
    import field 'T3' could not be found in one or more records.
    WeeWX field 'extraTemp3' will be set to 'None' in these records.
    Warning: Import field 'H1' is mapped to WeeWX field 'extraHumid1' but the
    import field 'H1' could not be found in one or more records.
    WeeWX field 'extraHumid1' will be set to 'None' in these records.
    Warning: Import field 'H2' is mapped to WeeWX field 'extraHumid2' but the
    import field 'H2' could not be found in one or more records.
    WeeWX field 'extraHumid2' will be set to 'None' in these records.
    Warning: Import field 'Sm1' is mapped to WeeWX field 'soilMoist1' but the
    import field 'Sm1' could not be found in one or more records.
    WeeWX field 'soilMoist1' will be set to 'None' in these records.
    Warning: Import field 'Sm2' is mapped to WeeWX field 'soilMoist2' but the
    import field 'Sm2' could not be found in one or more records.
    WeeWX field 'soilMoist2' will be set to 'None' in these records.
    Warning: Import field 'Sm3' is mapped to WeeWX field 'soilMoist3' but the
    import field 'Sm3' could not be found in one or more records.
    WeeWX field 'soilMoist3' will be set to 'None' in these records.
    Warning: Import field 'Sm4' is mapped to WeeWX field 'soilMoist4' but the
    import field 'Sm4' could not be found in one or more records.
    WeeWX field 'soilMoist4' will be set to 'None' in these records.
    Warning: Import field 'Lw1' is mapped to WeeWX field 'leafWet1' but the
    import field 'Lw1' could not be found in one or more records.
    WeeWX field 'leafWet1' will be set to 'None' in these records.
    Warning: Import field 'Lw2' is mapped to WeeWX field 'leafWet2' but the
    import field 'Lw2' could not be found in one or more records.
    WeeWX field 'leafWet2' will be set to 'None' in these records.
    Warning: Import field 'St1' is mapped to WeeWX field 'soilTemp1' but the
    import field 'St1' could not be found in one or more records.
    WeeWX field 'soilTemp1' will be set to 'None' in these records.
    Warning: Import field 'St2' is mapped to WeeWX field 'soilTemp2' but the
    import field 'St2' could not be found in one or more records.
    WeeWX field 'soilTemp2' will be set to 'None' in these records.
    Warning: Import field 'St3' is mapped to WeeWX field 'soilTemp3' but the
    import field 'St3' could not be found in one or more records.
    WeeWX field 'soilTemp3' will be set to 'None' in these records.
    Warning: Import field 'St4' is mapped to WeeWX field 'soilTemp4' but the
    import field 'St4' could not be found in one or more records.
    WeeWX field 'soilTemp4' will be set to 'None' in these records.
    Warning: Import field 'Lt1' is mapped to WeeWX field 'leafTemp1' but the
    import field 'Lt1' could not be found in one or more records.
    WeeWX field 'leafTemp1' will be set to 'None' in these records.
    Warning: Import field 'Lt2' is mapped to WeeWX field 'leafTemp2' but the
    import field 'Lt2' could not be found in one or more records.
    WeeWX field 'leafTemp2' will be set to 'None' in these records.
    Unique records processed: 38284; Last timestamp: 2016-11-30 23:59:00 AEST (1480514340)
    
    ... (identical entries for periods 3 to 7 omitted for conciseness)
    
    Period 8 ...
    Warning: Import field 'T1' is mapped to WeeWX field 'extraTemp1' but the
    import field 'T1' could not be found in one or more records.
    WeeWX field 'extraTemp1' will be set to 'None' in these records.
    Warning: Import field 'T2' is mapped to WeeWX field 'extraTemp2' but the
    import field 'T2' could not be found in one or more records.
    WeeWX field 'extraTemp2' will be set to 'None' in these records.
    Warning: Import field 'T3' is mapped to WeeWX field 'extraTemp3' but the
    import field 'T3' could not be found in one or more records.
    WeeWX field 'extraTemp3' will be set to 'None' in these records.
    Warning: Import field 'H1' is mapped to WeeWX field 'extraHumid1' but the
    import field 'H1' could not be found in one or more records.
    WeeWX field 'extraHumid1' will be set to 'None' in these records.
    Warning: Import field 'H2' is mapped to WeeWX field 'extraHumid2' but the
    import field 'H2' could not be found in one or more records.
    WeeWX field 'extraHumid2' will be set to 'None' in these records.
    Warning: Import field 'Sm1' is mapped to WeeWX field 'soilMoist1' but the
    import field 'Sm1' could not be found in one or more records.
    WeeWX field 'soilMoist1' will be set to 'None' in these records.
    Warning: Import field 'Sm2' is mapped to WeeWX field 'soilMoist2' but the
    import field 'Sm2' could not be found in one or more records.
    WeeWX field 'soilMoist2' will be set to 'None' in these records.
    Warning: Import field 'Sm3' is mapped to WeeWX field 'soilMoist3' but the
    import field 'Sm3' could not be found in one or more records.
    WeeWX field 'soilMoist3' will be set to 'None' in these records.
    Warning: Import field 'Sm4' is mapped to WeeWX field 'soilMoist4' but the
    import field 'Sm4' could not be found in one or more records.
    WeeWX field 'soilMoist4' will be set to 'None' in these records.
    Warning: Import field 'Lw1' is mapped to WeeWX field 'leafWet1' but the
    import field 'Lw1' could not be found in one or more records.
    WeeWX field 'leafWet1' will be set to 'None' in these records.
    Warning: Import field 'Lw2' is mapped to WeeWX field 'leafWet2' but the
    import field 'Lw2' could not be found in one or more records.
    WeeWX field 'leafWet2' will be set to 'None' in these records.
    Warning: Import field 'St1' is mapped to WeeWX field 'soilTemp1' but the
    import field 'St1' could not be found in one or more records.
    WeeWX field 'soilTemp1' will be set to 'None' in these records.
    Warning: Import field 'St2' is mapped to WeeWX field 'soilTemp2' but the
    import field 'St2' could not be found in one or more records.
    WeeWX field 'soilTemp2' will be set to 'None' in these records.
    Warning: Import field 'St3' is mapped to WeeWX field 'soilTemp3' but the
    import field 'St3' could not be found in one or more records.
    WeeWX field 'soilTemp3' will be set to 'None' in these records.
    Warning: Import field 'St4' is mapped to WeeWX field 'soilTemp4' but the
    import field 'St4' could not be found in one or more records.
    WeeWX field 'soilTemp4' will be set to 'None' in these records.
    Warning: Import field 'Lt1' is mapped to WeeWX field 'leafTemp1' but the
    import field 'Lt1' could not be found in one or more records.
    WeeWX field 'leafTemp1' will be set to 'None' in these records.
    Warning: Import field 'Lt2' is mapped to WeeWX field 'leafTemp2' but the
    import field 'Lt2' could not be found in one or more records.
    WeeWX field 'leafTemp2' will be set to 'None' in these records.
    Unique records processed: 38284; Last timestamp: 2017-06-30 23:59:00 AEST (1498831140)
    Finished dry run import
    308670 records were processed and 308670 unique records would have been imported.
    ```

    In this case warnings are evident for numerous import/WeeWX field pairs 
    that are mapped but for which no data could be found. If the warnings 
    relate to fields that are not included in the import source data the 
    warning may be safely ignored. If the warning relate to fields the user 
    expects to be in the import source data the issue should be investigated 
    further before the import is completed.

7. Once the dry run results are satisfactory the data can be imported using 
   the following command:

    ```
    weectl import --import-config=/var/tmp/wcat.conf --suppress-warnings
    ```
    
    This will result in a preamble similar to that of a dry run. At the end 
    of the preamble there will be a prompt:
    
    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    WeatherCat monthly .cat files in the  '/var/tmp/wcat' directory will be imported
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    Starting import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Proceeding will save all imported records in the WeeWX archive.
    Are you sure you want to proceed (y/n)?
    ```
    
    If there is more than one WeatherCat monthly .cat file the `import` 
    utility will provide summary information on a per period basis during the 
    import. In addition, if the `--date` option is used the source data that 
    falls outside the date or date range specified with the `--date` option 
    is ignored. In such cases the preamble may look similar to:
    
    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    WeatherCat monthly .cat files in the '/var/tmp/wcat' directory will be imported
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    Starting import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Period 1 - no records identified for import.
    Period 2 ...
    Period 2 - no records identified for import.
    Period 3 ...
    Proceeding will save all imported records in the WeeWX archive.
    Are you sure you want to proceed (y/n)?
    ```

8. If the import parameters are acceptable enter `y` to proceed with the 
   import or `n` to abort the import. If the import is confirmed, the source 
   data will be imported, processed and saved in the WeeWX database.
   Information on the progress of the import will be displayed similar to the 
   following:

    ```
    Unique records processed: 2305; Last timestamp: 2016-12-30 00:00:00 AEST (1483020000)
    ```
    
    Again if there is more than one WeatherCat monthly .cat file and if the 
    `--date` option is used the progress information may instead look similar 
    to:
    
    ```
    Period 4 ...
    Unique records processed: 8908; Last timestamp: 2017-01-31 23:59:00 AEST (1485870900)
    Period 5 ...
    Unique records processed: 8029; Last timestamp: 2017-02-28 23:59:00 AEST (1488290100)
    Period 6 ...
    Unique records processed: 8744; Last timestamp: 2017-03-31 23:59:00 AEST (1490968500)
    ```
    
    !!! Note
        Any periods for which no data could be obtained will be skipped. The 
        lack of data may be due to a missing WeatherCat monthly .cat file. A 
        short explanatory note to this effect will be displayed against the 
        period concerned and an entry included in the log.
    
    The line commencing with `Unique records processed` should update as 
   records are imported with progress information on number of records 
   processed, the number of unique records imported and the date-time of the 
   latest record processed. If the import spans multiple months (ie multiple 
   monthly .cat files) a new `Period` line is created for each month.
    
    Once the initial import is complete the `import` utility will, if 
    requested, calculate any missing derived observations and rebuild the 
    daily summaries. A brief summary should be displayed similar to the 
    following:
    
    ```
    Calculating missing derived observations ...
    Processing record: 77782; Last record: 2017-06-30 00:00:00 AEST (1519826400)
    Recalculating daily summaries...
    Records processed: 77000; Last date: 2017-06-28 11:45:00 AEST (1519811100)
    Finished recalculating daily summaries
    Finished calculating missing derived observations
    ```
    
    When the import is complete a brief summary is displayed similar to the 
    following:
    
    ```
    Finished import
    308670 records were processed and  08670 unique records imported in 1907.61 seconds.
    Those records with a timestamp already in the archive will not have been
    imported. Confirm successful import in the WeeWX log file.
    ```

9. Whilst the `import` utility will advise of the number of unique records 
   imported, it does not know how many, if any, of the imported records were 
   successfully saved to the database. You should look carefully through the 
   WeeWX log file covering the import session and take note of any records 
   that were not imported. The most common reason for imported records not 
   being saved to the database is because a record with that timestamp 
   already exists in the database, in such cases something similar to the 
   following will be found in the log:

    ```
    2023-11-04 15:33:01 weectl-import[3795]: ERROR weewx.manager: Unable to add record 2018-09-04 04:20:00 AEST (1535998800) to database 'weewx.sdb': UNIQUE constraint failed: archive.dateTime
    ```
    
    In such cases take note of the timestamp of the record(s) concerned and 
    make a decision about whether to delete the pre-existing record and 
    re-import the record or retain the pre-existing record.
