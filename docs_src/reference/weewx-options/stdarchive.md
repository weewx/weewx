# [StdArchive]

The `StdArchive` service stores data into a database.

#### ==archive_interval==

If your station hardware supports data logging then the archive interval will
be downloaded from the station. Otherwise, you must specify it here in
seconds, and it must be evenly divisible by 60. Optional. Default is `300`.

#### archive_delay

How long to wait in seconds after the top of an archiving interval before
fetching new data off the station. For example, if your archive interval is
5 minutes and archive_delay is set to 15, then the data will be fetched at
00:00:15, 00:05:15, 00:10:15, etc. This delay is to give the station a few
seconds to archive the data internally, and in case your server has any other
tasks to do at the top of the minute. Default is `15`.

#### record_generation

Set to whether records should be downloaded off the hardware (recommended),
or generated in software. If set to `hardware`, then WeeWX tries to download
archive records from your station. However, not all types of stations support
this, in which case WeeWX falls back to software generation. A setting of
`hardware` will work for most users. A notable exception is [users who have
cobbled together homebrew serial interfaces](https://www.wxforum.net/index.php?topic=10315.0)
for the Vantage stations that do not include memory for a logger. These users
should set this option to `software`, forcing software record generation.
Default is `hardware`.

#### record_augmentation

When performing hardware record generation, this option will attempt to
augment the record with any additional observation types that it can extract
out of the LOOP packets. Default is `true`.

#### no_catchup

Many weather stations have internal memory that can continue to record weather
data even when WeeWX is not running. Normally, when WeeWX starts up, it will
download this data and archive it. However, if you set this option to `true`,
then WeeWX will not attempt to catch up. Default is `false`.

#### loop_hilo

Set to `true` to have LOOP data and archive data to be used for high / low
statistics. Set to `false` to have only archive data used. If your sensor
emits lots of spiky data, setting to `false` may help. Default is `true`.

#### log_success

If you set a value for `log_success` here, it will override the value set at
the [top-level](general.md#log_success)  and will apply only to archiving
operations.

#### log_failure

If you set a value for `log_failure` here, it will override the value set at
the [top-level](general.md#log_failure)  and will apply only to archiving
operations.

#### data_binding

The data binding to be used to store the data. This should match one of the
bindings in the [`[DataBindings]`](data-bindings.md) section. Optional.
Default is `wx_binding`.
