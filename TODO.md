# To do

Use POST for station registry (instead of GET).

## Debian packaging

Test upgrade process.
- Upgrade from v4 Python 2
- Upgrade from v4 Python 3
- Upgrade from V5 to a later V5

## Documentation


## Drivers

## Utilities

Lot of inconsistencies in how the path to the config file is handled. Some utilities accept a
command line option, others require `--config=`.

Remove wunderfixer and its documentation.

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.

Update the logging wiki.


## Documentation


Put legacy (V4.x) docs at weewx.com/legacy_docs.



## Testing


## Upgrade guide

How to switch from init.d to systemd.

How to upgrade from V4 using Python 2 to V5.


## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549