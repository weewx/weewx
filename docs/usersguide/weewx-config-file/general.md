# General options

The options declared at the top are not part of any section.

#### ==debug==

Set to `1` to have the program perform extra debug checks, as well as emit extra information in the log file. This is strongly recommended if you are having trouble. Set to `2` for even more information. Otherwise, set to `0`. Default is `0` (no debug).

#### WEEWX_ROOT

Set to the root directory of the WeeWX file hierarchy for this station. Normally, this is set automatically by the installation process. Required. No default.

#### USER_ROOT

The location of the user package, relative to `WEEWX_ROOT`. WeeWX will look for any user-installed extensions in this directory. Default is `bin/user`.

#### ==log_success==

If set to `true`, the default will be to log a successful operation (for example, the completion of a report, or uploading to the Weather Underground, etc.) to the system log. Default is `true`.

#### ==log_failure==

If set to `true`, the default will be to log an unsuccessful operation (for example, failure to generate a report, or failure to upload to the Weather Underground, etc.) to the system log. Default is `true`.

#### socket_timeout

Set to how long to wait in seconds before declaring a socket time out. This is used by many services such as FTP, or the uploaders. Twenty (20) seconds is reasonable. Default is `20`.

#### gc_interval

Set to how often garbage collection should be performed in seconds by the Python runtime engine. Default is every `10800` (3 hours).

#### loop_on_init

Normally, if a hardware driver fails to load, WeeWX will exit, on the assumption that there is likely a configuration problem and so retries are useless. However, in some cases, drivers can fail to load for intermittent reasons, such as a network failure. In these cases, it may be useful to have WeeWX do a retry. Setting this option to `true` will cause WeeWX to keep retrying indefinitely. Default is `false`.`