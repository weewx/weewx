# General
The options declared at the top are not actually part of any section.

## debug

Set to 1 to have the program perform extra debug checks, as well as emit extra information in the log file. This is strongly recommended if you are having trouble. Otherwise, set to 0. Default is 0 (no debug).

## WEEWX_ROOT

Set to the root directory of the WeeWX file hierarchy for this station. Normally, this is set automatically by the installation process. Required. No default.

## log_success

If set to true, the default will be to log a successful operation (for example, the completion of a report, or uploading to the Weather Underground, etc.) to the system log. Default is **true**.

## log_failure

If set to **true**, the default will be to log an unsuccessful operation (for example, failure to generate a report, or failure to upload to the Weather Underground, etc.) to the system log. Default is **true**.

## socket_timeout

Set to how long to wait before declaring a socket time out. This is used when using FTP to send data to a web server or when sending data to the Weather Underground. Twenty (20) seconds is reasonable. Default is 20.

## gc_interval

Set to how often garbage collection should be performed by the Python runtime engine. Default is every 10,800 seconds (3 hours).

## loop_on_init

Normally, if the hardware driver fails to load, WeeWX will exit. The assumption is that there is a configuration problem and so retries are useless. However, in some cases, drivers can fail to load for intermittent reasons, such as a network failure. In these cases, it may be useful to have WeeWX do a retry. Setting this option to 1 will cause WeeWX to keep retrying indefinitely.