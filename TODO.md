# To do


## Commands
```
✅ weectl station create
✅ weectl station reconfigure
✅ weectl station upgrade
✅ weectl station upgrade-skins
✅ weectl extension install
✅ weectl extension uninstall
✅ weectl extension list
✅ weectl extension transfer
```
Key: 
✅ means completed
½ means started

## Utilities

Remove wunderfixer and its documentation.

## Logging

Consider making `$HOME/weewx-data/logs` the default log for MacOS.

Update the logging wiki.


## Documentation

Fill out "Preparation" section in pip.md for RedHat, SuSE, and macOS.

Put legacy (V4.x) docs at weewx.com/legacy_docs.


## Examples

Update the examples:

- ~~basic~~
- ~~colorize_1~~
- ~~colorize_2~~
- ~~colorize_3~~
- ~~fileparse~~
- ~~pmon~~
- xstats
- alarm.py
- lowBattery.py
- mem.py
- seven_day.py
- transfer_db.py
- vaporpressure.py



## Testing


## Upgrade guide

How to switch from init.d to systemd.


## Miscellaneous

Should change the station registry uploader to use `~` instead of the absolute path to the user's
home directory. See Slack: https://weewx.slack.com/archives/C04AEC3K4G7/p1673192099682549