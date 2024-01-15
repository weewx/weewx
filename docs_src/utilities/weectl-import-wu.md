!!! Warning
    Running WeeWX during a `weectl import` session can lead to abnormal 
    termination of the import. If WeeWX must remain running (e.g., so that 
    live data is not lost) run the `weectl import` session on another 
    machine or to a second database and merge the in-use and second 
    database once the import is complete.

`weectl import` can import historical observation data for a Weather 
Underground PWS via the Weather Underground API. The Weather Underground API 
provides historical weather station observations received by Weather 
Underground for the PWS concerned on a day by day basis. As such, the data is 
analogous to the WeeWX archive table. When `weectl import` imports data from 
the Weather Underground API each day is considered a 'period'. `weectl 
import` processes one period at a time in chronological order (oldest to 
newest) and provides import summary data on a per period basis.

## Mapping data to archive fields

A Weather Underground import will populate WeeWX archive fields as follows:

* Provided data exists for each field returned by the Weather Underground 
  API, the following WeeWX archive fields will be directly populated by 
  imported data:

    * `dateTime`
    * `barometer`
    * `dewpoint`
    * `heatindex`
    * `outHumidity`
    * `outTemp`
    * `radiation`
    * `rain`
    * `rainRate`
    * `UV`
    * `windchill`
    * `windDir`
    * `windGust`
    * `windSpeed`

    !!! Note
        If an appropriate field is not returned by the Weather Underground 
        API the corresponding WeeWX archive field will contain no data. If 
        the API returns an appropriate field but with no data, the 
        corresponding WeeWX archive field will be set to `None/null`. For 
        example, if the API response has no solar radiation field the WeeWX 
        `radiation` archive field will have no data stored. However, if the 
        API response has a solar radiation field but contains no data, the 
        WeeWX `radiation` archive field will be `None/null`.

* The following WeeWX archive fields will be populated from other settings or 
  configuration options:

    * `interval`
    * `usUnits`

* The following WeeWX archive fields will be populated with values derived 
  from the imported data provided `calc_missing = True` is included in the 
  `[WU]` section of the import configuration file and the field exists in the 
  in-use WeeWX archive table schema.

    * `altimeter`
    * `ET`
    * `pressure`

!!! Note
    If `calc_missing = False` is included in the `[WU]` section of the 
    import configuration file being used then all of the above fields will be 
    set to `None/null`. The `calc_missing` option default is `True`.


## Step-by-step instructions

To import observations from a Weather Underground PWS history:

1. Obtain the weather station ID of the Weather Underground PWS from which 
   data is to be imported. The station ID will be a sequence of numbers and 
   upper case letters that is usually 11 or 12 characters in length. For the 
   purposes of the following examples a weather station ID of `ISTATION123` 
   will be used.

2. Obtain the API key to be used to access the Weather Underground API. This 
   will be a seemingly random alphanumeric sequence of 32 characters. API 
   keys are available to Weather Underground PWS contributors by logging on
   to their Weather Underground account and accessing Member Settings.

3. Make a backup of the WeeWX database in case the import should go awry.

4. Create an import configuration file. In this case we will make a copy of 
   the example Weather Underground import configuration file and save it as 
   `wu.conf` in the `/var/tmp` directory:

    ```
    cp /home/weewx/util/import/wu-example.conf /var/tmp/wu.conf
    ```

5. Open `wu.conf` and:

    * confirm the [`source`](weectl-import-config-opt.md#import_config_source)
      option is set to `WU`:

        ```
        source = WU
        ```

    * confirm the following options in the `[WU]` section are correctly set:

        * [station_id](weectl-import-config-opt.md#wu_station_id). The 11 or 
          12 character weather station ID of the Weather Underground PWS that 
          will be the source of the imported data.

        * [api_key](weectl-import-config-opt.md#wu_api_key). The 32 character 
          API key to be used to access the Weather Underground API.

        * [interval](weectl-import-config-opt.md#wu_interval). Determines how 
          the WeeWX interval field is derived.

        * [qc](weectl-import-config-opt.md#wu_qc). Determines whether quality 
          control checks are performed on the imported data.

            !!! Note
                As Weather Underground imports at times contain nonsense 
                values, particularly for fields for which no data were 
                uploaded to Weather Underground by the PWS, the use of 
                quality control checks on imported data can prevent these 
                nonsense values from being imported and contaminating the 
                WeeWX database.

        * [calc_missing](weectl-import-config-opt.md#wu_calc_missing). 
          Determines whether missing derived observations will be calculated 
          from the imported data.

        * [ignore_invalid_data](weectl-import-config-opt.md#wu_ignore_invalid_data). 
          Determines whether invalid data in a source field is ignored or the 
          import aborted

        * [tranche](weectl-import-config-opt.md#wu_tranche). The number of 
          records written to the WeeWX database in each transaction.

        * [wind_direction](weectl-import-config-opt.md#wu_wind_direction). 
          Determines how imported wind direction fields are interpreted.

        * [[[FieldMap]]](weectl-import-config-opt.md#wu_fieldmap). Defines 
          the mapping between imported data fields and WeeWX archive fields. 
 
6. When first importing data it is prudent to do a dry run import before any 
   data is actually imported. A dry run import will perform all steps of the 
   import without actually writing imported data to the WeeWX database. In 
   addition, consideration should be given to any additional options to be 
   used such as `--date`, `--from` or `--to`.
                
    To perform a dry run enter the following command:

    ```
    weectl import --import-config=/var/tmp/wu.conf --from=2016-01-20T22:30 --to=2016-01-23T06:00 --dry-run
    ```

    In this case the `--from` and `--to` options have been used to import 
   Weather Underground records from 10:30pm on 20 January 2016 to 6:00am 
   on 23 January 2016 inclusive.

    !!! Note
        If the `--date` option is omitted, or a date (not date-time) range 
        is specified using the `--from` and `--to` options during a Weather 
        Underground import, then one or more full days of history data will 
        be imported. This includes records timestamped from `00:00` 
        (inclusive) at the start of the day up to but NOT including the 
        `00:00` record at the end of the last day. As the timestamped record 
        refers to observations of the previous interval, such an import 
        actually includes one record with observations from the previous day 
        (the `00:00` record at the start of the day). Whilst this will not 
        present a problem for `weectl import` as any records being imported 
        with a timestamp that already exists in the WeeWX database are 
        ignored, you may wish to use the `--from` and `--to` options with a 
        suitable date-time range to precisely control which records are 
        imported.

    !!! Note
        `weectl import` obtains Weather Underground daily history data one 
        day at a time via a HTTP request and as such the import of large time 
        spans of data may take some time. Such imports may be best handled as 
        a series of imports of smaller time spans.
    
    This will result in a short preamble with details on the data source, the 
   destination of the imported data and some other details on how the data 
   will be processed. The import will then be performed but no data will be 
   written to the WeeWX database.
    
    The output should be similar to:
    
    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    Observation history for Weather Underground station 'ISTATION123' will be imported.
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    Observations timestamped after 2016-01-20 22:30:00 AEST (1453293000) and up to and including 2016-01-23 06:00:00 AEST (1453492800) will be imported.
    This is a dry run, imported data will not be saved to archive.
    Starting dry run import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Unique records processed: 18; Last timestamp: 2016-01-20 23:55:00 AEST (1453298100)
    Period 2 ...
    Unique records processed: 284; Last timestamp: 2016-01-21 23:55:00 AEST (1453384500)
    Period 3 ...
    Unique records processed: 284; Last timestamp: 2016-01-22 23:55:00 AEST (1453470900)
    Period 4 ...
    Unique records processed: 71; Last timestamp: 2016-01-23 06:00:00 AEST (1453492800)
    Finished dry run import
    657 records were processed and 657 unique records would have been imported.
    ```

    !!! Note
        Any periods for which no data could be obtained will be skipped. 
        The lack of data may be due to an incorrect station ID, an incorrect 
        date or Weather Underground API problems. A short explanatory note to 
        this effect will be displayed against the period concerned and an 
        entry included in the log.

7. Once the dry run results are satisfactory the source data can be imported 
   using the following command:

    ```
    weectl import --import-config=/var/tmp/wu.conf --from=2016-01-20T22:30 --to=2016-01-23T06:00
    ```

    This will result in a short preamble similar to that of a dry run. At the 
   end of the preamble there will be a prompt:
    
    ```
    Using WeeWX configuration file /home/weewx/www-data/weewx.conf
    Starting weectl import...
    Observation history for Weather Underground station 'ISTATION123' will be imported.
    Using database binding 'wx_binding', which is bound to database 'weewx.sdb'
    Destination table 'archive' unit system is '0x01' (US).
    Missing derived observations will be calculated.
    Observations timestamped after 2016-01-20 22:30:00 AEST (1453293000) and up to and including 2016-01-23 06:00:00 AEST (1453492800) will be imported.
    Starting import ...
    Records covering multiple periods have been identified for import.
    Period 1 ...
    Proceeding will save all imported records in the WeeWX archive.
    Are you sure you want to proceed (y/n)?
    ```
    
    !!! Note
        `weectl import` obtains Weather Underground data one day at a time 
        via a HTTP request and as such the import of large time spans of data 
        may take some time. Such imports may be best handled as a series of 
        imports of smaller time spans.

8. If the import parameters are acceptable enter `y` to proceed with the 
   import or `n` to abort the import. If the import is confirmed, the 
   source data will be imported, processed and saved in the WeeWX database.
   Information on the progress of the import will be displayed similar to 
   the following:

    ```
    Unique records processed: 18; Last timestamp: 2016-01-20 23:55:00 AEST (1453298100)
    Period 2 ...
    Unique records processed: 284; Last timestamp: 2016-01-21 23:55:00 AEST (1453384500)
    Period 3 ...
    Unique records processed: 284; Last timestamp: 2016-01-22 23:55:00 AEST (1453470900)
    ```
    
    !!! Note
        Any periods for which no data could be obtained will be skipped. The 
        lack of data may be due to an incorrect station ID, an incorrect date 
        or Weather Underground API problems. A short explanatory note to this 
        effect will be displayed against the period concerned and an entry 
        included in the log.
    
    The line commencing with `Unique records processed` should update as 
   records are imported with progress information on number of records 
   processed, number of unique records imported and the date time of the 
   latest record processed. If the import spans multiple days then a new 
   `Period` line is created for each day.
    
    Once the initial import is complete `weectl import` will, if requested, 
   calculate any missing derived observations and rebuild the daily 
   summaries. A brief summary should be displayed similar to the following:
    
    ```
    Calculating missing derived observations ...
    Processing record: 204; Last record: 2016-01-22 23:55:00 AEST (1453470900)
    Recalculating daily summaries...
    Finished recalculating daily summaries
    Finished calculating missing derived observations
    ```
    
    When the import is complete a brief summary is displayed similar to 
   the following:
    
    ```
    Finished import
    657 records were processed and 657 unique records imported in 78.97 seconds.
    Those records with a timestamp already in the archive will not have been 
    imported. Confirm successful import in the WeeWX log file.
    ```
    
    !!! Note
        The new (2019) Weather Underground API appears to have an issue 
        when obtaining historical data for the current day. The first time 
        the API is queried the API returns all historical data up to and 
        including the most recent record. However, subsequent later API 
        queries during the same day return the same set of records rather 
        than all records up to and including the time of the latest API 
        query. Users importing Weather Underground data that includes data 
        from the current day are advised to carefully check the WeeWX log 
        to ensure that all expected records were imported. If some records 
        are missing from the current day try running an import for the 
        current day again using the `--date` option setting. If this fails 
        then wait until the following day and perform another import for 
        the day concerned again using the `--date` option setting. In all 
        cases confirm what data has been imported by referring to the 
        WeeWX log.

9. Whilst `weectl import` will advise of the number of records processed and 
   the number of unique records found, `weectl import` does know how many, if 
   any, of the imported records were successfully saved to the database. You 
   should look carefully through the WeeWX log file covering the `weectl 
   import` session and take note of any records that were not imported. The 
   most common reason for imported records not being saved to the database 
   is because a record with that timestamp already exists in the database, 
   in such cases something similar to the following will be found in the log:

    ```
    2023-11-04 15:33:01 weectl-import[3795]: ERROR weewx.manager: Unable to add record 2018-09-04 04:20:00 AEST (1535998800) to database 'weewx.sdb': UNIQUE constraint failed: archive.dateTime
    ```
    
    In such cases you should take note of the timestamp of the record(s) 
   concerned and make a decision about whether to delete the pre-existing 
   record and re-import the record or retain the pre-existing record.
